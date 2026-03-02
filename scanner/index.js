import fs from 'fs/promises';
import { Telegraf } from 'telegraf';
import { MongoClient } from 'mongodb';
import { getJobTitlesByFakeBrowser, getJobTitlesByAxios } from './jobTitleParser.js';

const MONGODB_URI = 'mongodb://mongo:27017';
const SOURCES_FILE = './config/sources.json';
const DEEP_SCAN_DAYS = 180;

const init = async () => {
  const config = JSON.parse(await fs.readFile('./config/default.json', 'utf8'));
  const jobSites = JSON.parse(await fs.readFile('./config/jobSites.json', 'utf8'));
  let sources = [];
  try {
    sources = JSON.parse(await fs.readFile(SOURCES_FILE, 'utf8'));
  } catch {
    // sources.json not present — stats tracking disabled
  }
  return { config, jobSites, sources };
};

const saveSourceStats = async (sources) => {
  try {
    await fs.writeFile(SOURCES_FILE, JSON.stringify(sources, null, 2));
  } catch (e) {
    console.error('[scanner] Failed to save source stats:', e.message);
  }
};

const parseJobSites = async (config, jobSites, sources, telegramBot) => {
  const mongo = await MongoClient.connect(MONGODB_URI, { useNewUrlParser: true });
  const db = mongo.db('jobnotifications');
  const col = db.collection('viewedJobTitles');

  const now = new Date();
  const deepScanCutoff = new Date(now.getTime() - DEEP_SCAN_DAYS * 24 * 60 * 60 * 1000);
  let sourcesUpdated = false;

  jobSites.sort((a, b) => (b.priority ?? 5) - (a.priority ?? 5));

  for await (const site of jobSites) {
    const source = sources.find(s => s.url === site.url);
    const isFirstScan = source && !source.stats?.last_scan;

    if (isFirstScan) {
      console.info(`[scanner] ${site.name}: first scan — deep mode (${DEEP_SCAN_DAYS}d lookback)`);
    }

    let listingsCount = 0;
    let newVacanciesCount = 0;
    let failed = false;

    try {
      const usesFakeBrowser = site.scan_method === 'fakebrowser' || site.antiBotCheck;
      const jobTitles = usesFakeBrowser
        ? await getJobTitlesByFakeBrowser(site)
        : await getJobTitlesByAxios(site);

      listingsCount = jobTitles.length;
      console.info(`[scanner] ${site.name}: ${listingsCount} listings`);

      for (const raw of jobTitles) {
        const jobTitle = raw.toLowerCase().trim();
        const isMatch = config.JOB_KEYWORDS.some(kw => jobTitle.includes(kw.toLowerCase()));
        if (!isMatch) continue;

        // Deep scan: skip only if seen within last 180 days.
        // Normal scan: skip if ever seen.
        const query = isFirstScan
          ? { title: jobTitle, site: site.url, date: { $gt: deepScanCutoff } }
          : { title: jobTitle, site: site.url };

        const alreadySeen = await col.findOne(query);
        if (!alreadySeen) {
          newVacanciesCount++;
          const msg = `🚀 New ${jobTitle.toUpperCase()} on ${site.name}: ${site.url}`;
          console.info(msg);
          await telegramBot.telegram.sendMessage(config.TELEGRAM.CHAT_ID, msg);
          await col.insertOne({ title: jobTitle, site: site.url, date: now });
        }
      }
    } catch (error) {
      console.error(`[scanner] ${site.name} error:`, error.message);
      failed = true;
    }

    if (source) {
      if (!source.stats) source.stats = {};
      source.stats.last_scan = now.toISOString();
      source.stats.last_listings_count = failed ? source.stats.last_listings_count ?? null : listingsCount;

      if (failed) {
        source.stats.consecutive_failures = (source.stats.consecutive_failures ?? 0) + 1;
      } else {
        source.stats.consecutive_failures = 0;
        if (newVacanciesCount > 0) {
          source.stats.total_vacancies_found = (source.stats.total_vacancies_found ?? 0) + newVacanciesCount;
          source.stats.last_new_vacancy = now.toISOString();
        }
      }
      sourcesUpdated = true;
    }
  }

  await mongo.close();

  if (sourcesUpdated) {
    await saveSourceStats(sources);
  }

  if (global.gc) global.gc();
};

(async () => {
  const { config: baseConfig } = await init();
  const telegramBot = new Telegraf(baseConfig.TELEGRAM.TOKEN);
  // Polling disabled — OpenClaw handles all incoming messages

  const runScan = async () => {
    const { config, jobSites, sources } = await init();
    await parseJobSites(config, jobSites, sources, telegramBot);
  };

  await runScan();
  setInterval(runScan, baseConfig.SCAN_INTERVAL_MINUTES * 60 * 1000);
})();
