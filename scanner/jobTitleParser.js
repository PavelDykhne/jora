import axios from 'axios';
import cheerio from 'cheerio';
import { faker } from '@faker-js/faker';
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';

puppeteer.use(StealthPlugin());

const getJobTitlesByFakeBrowser = async (site) => {
  const selector = site.config?.jobTitleSelector || site.jobTitleSelector;
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  let jobTitles = [];

  try {
    const page = await browser.newPage();
    await page.goto(site.url, { waitUntil: 'networkidle2', timeout: 30000 });
    jobTitles = await page.$$eval(selector,
      elements => elements.map(item => item.textContent?.trim()).filter(Boolean));
    await browser.close();
  } catch (error) {
    console.error(`===============================Parsing ${site.name} returned ERROR:${error}===============================`);
    await browser.close().catch(() => {});
    return [];
  }
  return jobTitles;
}

const getJobTitlesByAxios = async (site) => {
  const selector = site.config?.jobTitleSelector || site.jobTitleSelector;
  try{
    const response = await axios.get(site.url, { headers: { 'User-Agent': faker.internet.userAgent() }  });
    const html = response.data;
    const $ = await cheerio.load(html);

    let jobTitles = [];
    const jobTitlesElements = await $(selector);
    for (let i = 0; i < jobTitlesElements.length; i++) {
      jobTitles[i] = $(jobTitlesElements[i]).text();
    }
    return jobTitles;
  }
  catch (error) {
    console.error(`===============================Parsing ${site.name} returned ERROR:${error}===============================`);
    return [];
  }
}

export { getJobTitlesByFakeBrowser, getJobTitlesByAxios };
