const database = db.getSiblingDB("crypto_pulse");
for (const name of ["trades_history", "history_imports", "trades", "trades_rejected", "news", "social_posts", "indicators", "alerts", "sentiment"]) {
  if (!database.getCollectionNames().includes(name)) database.createCollection(name);
}
database.trades_history.createIndex({ symbol: 1, trade_id: 1 }, { unique: true });
database.trades_history.createIndex({ symbol: 1, event_time: -1 });
database.trades.createIndex({ event_id: 1 }, { unique: true });
database.trades.createIndex({ symbol: 1, event_time: -1 });
database.trades_rejected.createIndex({ rejected_at: -1 });
database.news.createIndex({ event_id: 1 }, { unique: true });
database.social_posts.createIndex({ event_id: 1 }, { unique: true });
database.indicators.createIndex({ symbol: 1, event_time: -1 });
database.alerts.createIndex({ symbol: 1, event_time: -1 });
database.sentiment.createIndex({ event_id: 1 }, { unique: true });
print("CryptoPulse MongoDB collections and indexes ready");
