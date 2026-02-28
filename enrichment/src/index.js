/**
 * Enrichment Service
 * 
 * Watches MongoDB for new vacancies from job-scanner-tg,
 * enriches them with company data, detects fuzzy duplicates,
 * and sends enhanced notifications to Telegram.
 * 
 * Flow:
 * 1. job-scanner-tg finds vacancy → saves to MongoDB
 * 2. enrichment-svc detects new entry (poll every 60s)
 * 3. Checks for fuzzy duplicates
 * 4. Enriches with company data (Layer 2)
 * 5. Calculates relevance score
 * 6. Sends enhanced notification to TG
 */

const { MongoClient } = require('mongodb');
const stringSimilarity = require('string-similarity');
const { Telegraf } = require('telegraf');
const cron = require('node-cron');
const config = require('config');

// --- Config ---
const MONGO_URI = process.env.MONGO_URI || config.get('MONGO_URI');
const DB_NAME = process.env.DB_NAME || config.get('DB_NAME');
const TG_TOKEN = process.env.TG_TOKEN || config.get('TELEGRAM.TOKEN');
const TG_CHAT_ID = process.env.TG_CHAT_ID || config.get('TELEGRAM.CHAT_ID');
const DUPLICATE_THRESHOLD = parseFloat(process.env.DUPLICATE_THRESHOLD || config.get('DUPLICATE_THRESHOLD'));
const POLL_INTERVAL_MS = parseInt(process.env.POLL_INTERVAL_MS || '60000');

// --- Init ---
const bot = new Telegraf(TG_TOKEN);
let db;

async function connect() {
  const client = new MongoClient(MONGO_URI);
  await client.connect();
  db = client.db(DB_NAME);
  console.log(`[enrichment] Connected to MongoDB: ${DB_NAME}`);
  
  // Ensure indexes
  await db.collection('vacancies').createIndex({ enriched: 1 });
  await db.collection('vacancies').createIndex({ company: 1, title: 1 });
  await db.collection('vacancies').createIndex({ found_at: -1 });
}

// --- Fuzzy Duplicate Detection ---

async function findDuplicates(vacancy) {
  const candidates = await db.collection('vacancies')
    .find({
      _id: { $ne: vacancy._id },
      found_at: { $gte: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) } // last 90 days
    })
    .project({ title: 1, company: 1, url: 1, source: 1 })
    .toArray();

  const duplicates = [];
  
  for (const candidate of candidates) {
    // Combine company + title for matching
    const vacancyStr = `${vacancy.company || ''} ${vacancy.title}`.toLowerCase().trim();
    const candidateStr = `${candidate.company || ''} ${candidate.title}`.toLowerCase().trim();
    
    const similarity = stringSimilarity.compareTwoStrings(vacancyStr, candidateStr);
    
    if (similarity >= DUPLICATE_THRESHOLD) {
      duplicates.push({
        original_id: candidate._id,
        original_title: candidate.title,
        original_company: candidate.company,
        original_source: candidate.source,
        original_url: candidate.url,
        confidence: Math.round(similarity * 100)
      });
    }
  }
  
  return duplicates;
}

// --- Company Enrichment (Layer 2) ---

async function enrichCompany(companyName) {
  if (!companyName) return null;
  
  // Check cache first
  const cached = await db.collection('company_cache').findOne({
    name: companyName.toLowerCase(),
    cached_at: { $gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) } // 7 day cache
  });
  
  if (cached) return cached.data;
  
  // Basic enrichment from available data
  // In production, this would call external APIs (Crunchbase, Glassdoor, etc.)
  // For POC, we build a brief from the company name and any stored data
  const enrichment = {
    company_name: companyName,
    enriched_at: new Date().toISOString(),
    // These fields would be populated by API calls in production
    company_size: null,
    domain: null,
    hq: null,
    founded: null,
    funding: null,
    glassdoor_rating: null,
    tech_stack: [],
    recent_news: null,
    career_page: null,
    linkedin_url: null
  };
  
  // Cache the result
  await db.collection('company_cache').updateOne(
    { name: companyName.toLowerCase() },
    { $set: { name: companyName.toLowerCase(), data: enrichment, cached_at: new Date() } },
    { upsert: true }
  );
  
  return enrichment;
}

// --- Relevance Scoring ---

function calculateRelevanceScore(vacancy, keywords) {
  let score = 0;
  const title = (vacancy.title || '').toLowerCase();
  
  // Exact keyword match: +30 per match
  for (const keyword of keywords.exact_match || []) {
    if (title.includes(keyword.toLowerCase())) {
      score += 30;
      break;
    }
  }
  
  // Close variation match: +20 per match
  for (const keyword of keywords.close_variations || []) {
    if (title.includes(keyword.toLowerCase())) {
      score += 20;
      break;
    }
  }
  
  // Stretch match: +10 per match
  for (const keyword of keywords.stretch_titles || []) {
    if (title.includes(keyword.toLowerCase())) {
      score += 10;
      break;
    }
  }
  
  // Exclude pattern penalty: -50
  for (const pattern of keywords.exclude_patterns || []) {
    if (title.includes(pattern.toLowerCase())) {
      score -= 50;
    }
  }
  
  // Remote bonus: +10
  const text = `${vacancy.title} ${vacancy.raw_text || ''}`.toLowerCase();
  if (text.includes('remote') || text.includes('anywhere')) {
    score += 10;
  }
  
  // Known good domain bonus: +10
  const goodDomains = ['fintech', 'saas', 'platform', 'marketplace'];
  for (const domain of goodDomains) {
    if (text.includes(domain)) {
      score += 10;
      break;
    }
  }
  
  return Math.max(0, Math.min(100, score));
}

// --- Telegram Notifications ---

async function sendEnrichedNotification(vacancy, enrichment, duplicates, score) {
  let message = `🏢 *${escapeMarkdown(vacancy.company || 'Unknown')}*: ${escapeMarkdown(vacancy.title)}\n\n`;
  
  message += `📊 Relevance: ${score}/100\n`;
  message += `📍 Source: ${escapeMarkdown(vacancy.source || 'unknown')}\n`;
  message += `🔗 ${vacancy.url || 'No link'}\n`;
  
  // Company enrichment
  if (enrichment) {
    message += `\n🏢 *Company Brief:*\n`;
    if (enrichment.company_size) message += `👥 ${enrichment.company_size} employees\n`;
    if (enrichment.domain) message += `🏷 ${enrichment.domain}\n`;
    if (enrichment.hq) message += `📍 HQ: ${enrichment.hq}\n`;
    if (enrichment.glassdoor_rating) message += `⭐ Glassdoor: ${enrichment.glassdoor_rating}/5\n`;
    if (enrichment.career_page) message += `🔗 Careers: ${enrichment.career_page}\n`;
  }
  
  // Duplicates warning
  if (duplicates.length > 0) {
    message += `\n⚠️ *Possible duplicates:*\n`;
    for (const dup of duplicates.slice(0, 3)) {
      message += `• "${escapeMarkdown(dup.original_title)}" from ${escapeMarkdown(dup.original_source)} (${dup.confidence}%)\n`;
    }
  }
  
  message += `\n→ /docs\\_${vacancy._id} — подготовить документы`;
  
  try {
    await bot.telegram.sendMessage(TG_CHAT_ID, message, { parse_mode: 'Markdown' });
  } catch (err) {
    console.error('[enrichment] TG send error:', err.message);
    // Retry without markdown
    try {
      await bot.telegram.sendMessage(TG_CHAT_ID, message.replace(/[*_`]/g, ''));
    } catch (err2) {
      console.error('[enrichment] TG retry failed:', err2.message);
    }
  }
}

function escapeMarkdown(text) {
  return String(text || '').replace(/[_*[\]()~`>#+\-=|{}.!]/g, '\\$&');
}

// --- Main Poll Loop ---

async function processNewVacancies() {
  try {
    // Find vacancies that haven't been enriched yet
    const newVacancies = await db.collection('vacancies')
      .find({ enriched: { $ne: true } })
      .sort({ found_at: -1 })
      .limit(20)
      .toArray();
    
    if (newVacancies.length === 0) return;
    
    console.log(`[enrichment] Processing ${newVacancies.length} new vacancies`);
    
    // Load keywords
    let keywords = { exact_match: [], close_variations: [], stretch_titles: [], exclude_patterns: [] };
    try {
      const kw = await db.collection('config').findOne({ key: 'keywords' });
      if (kw) keywords = kw.value;
    } catch (e) {
      console.warn('[enrichment] No keywords config found, using defaults');
    }
    
    for (const vacancy of newVacancies) {
      // 1. Fuzzy duplicate check
      const duplicates = await findDuplicates(vacancy);
      
      // 2. Company enrichment
      const enrichment = await enrichCompany(vacancy.company);
      
      // 3. Relevance score
      const score = calculateRelevanceScore(vacancy, keywords);
      
      // 4. Update vacancy in DB
      await db.collection('vacancies').updateOne(
        { _id: vacancy._id },
        {
          $set: {
            enriched: true,
            enriched_at: new Date(),
            enrichment: enrichment,
            relevance_score: score,
            duplicate_of: duplicates.length > 0 ? duplicates[0].original_id : null,
            duplicate_confidence: duplicates.length > 0 ? duplicates[0].confidence : null,
            all_duplicates: duplicates
          }
        }
      );
      
      // 5. Send enhanced TG notification (only if score > threshold)
      const minScore = parseInt(process.env.RELEVANCE_SCORE_MIN || '0');
      if (score >= minScore) {
        await sendEnrichedNotification(vacancy, enrichment, duplicates, score);
      } else {
        console.log(`[enrichment] Skipped notification for "${vacancy.title}" (score ${score} < ${minScore})`);
      }
      
      // Rate limit: 1 second between notifications
      await new Promise(r => setTimeout(r, 1000));
    }
  } catch (err) {
    console.error('[enrichment] Processing error:', err);
  }
}

// --- Startup ---

async function main() {
  await connect();
  
  console.log(`[enrichment] Starting poll loop (every ${POLL_INTERVAL_MS / 1000}s)`);
  
  // Poll for new vacancies
  setInterval(processNewVacancies, POLL_INTERVAL_MS);
  
  // Initial run
  await processNewVacancies();
  
  console.log('[enrichment] Service ready');
}

main().catch(err => {
  console.error('[enrichment] Fatal error:', err);
  process.exit(1);
});
