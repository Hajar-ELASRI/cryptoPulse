package com.cryptopulse.api;
import org.bson.Document;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.aggregation.Aggregation;
import org.springframework.data.mongodb.core.aggregation.AggregationOperation;
import org.springframework.data.mongodb.core.aggregation.AggregationOptions;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.stereotype.Repository;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
@Repository
class MarketRepository {
    private final MongoTemplate mongo;
    MarketRepository(MongoTemplate mongo) { this.mongo = mongo; }
    List<Document> find(String collection, String timeField, MarketFilter filter) {
        return mongo.find(query(collection, timeField, filter), Document.class, collection);
    }
    static Query query(String collection, String timeField, MarketFilter f) {
        List<Criteria> clauses = new ArrayList<>();
        if (!collection.equals("sentiment")) {
            clauses.add(Criteria.where("run_id").is(f.runId()));
            clauses.add(Criteria.where("mode").is(f.runId().equals("live") ? "live" : "replay"));
        }
        if (f.symbol() != null) clauses.add(Criteria.where(collection.equals("sentiment") ? "trade_symbols" : "symbol").is(f.symbol()));
        if (f.type() != null) clauses.add(Criteria.where("type").is(f.type()));
        if (f.severity() != null) clauses.add(Criteria.where("severity").is(f.severity()));
        if (f.label() != null) clauses.add(Criteria.where("label").is(f.label()));
        if (f.from() != null || f.to() != null) {
            Criteria time = Criteria.where(timeField);
            if (f.from() != null) time.gte(Date.from(f.from()));
            if (f.to() != null) time.lt(Date.from(f.to()));
            clauses.add(time);
        }
        Query query = clauses.isEmpty() ? new Query() : new Query(new Criteria().andOperator(clauses));
        var direction = f.ascending() ? Sort.Direction.ASC : Sort.Direction.DESC;
        return query.with(Sort.by(direction, timeField, "_id")).skip((long) f.page() * f.limit()).limit(f.limit());
    }
    List<Document> runs(int page, int limit) {
        List<AggregationOperation> operations = runPipeline(page, limit).stream()
            .<AggregationOperation>map(document -> context -> document).toList();
        return mongo.aggregate(Aggregation.newAggregation(operations).withOptions(
            AggregationOptions.builder().maxTime(Duration.ofSeconds(5)).build()), "indicators", Document.class).getMappedResults();
    }
    static List<Document> runPipeline(int page, int limit) {
        Document match = new Document("mode", "replay").append("run_id", new Document("$type", "string").append("$nin", List.of("", "live")));
        Document indicators = new Document("run_id", 1).append("symbol", 1).append("start", "$window_start")
            .append("end", "$window_end").append("indicator_count", new Document("$literal", 1))
            .append("alert_count", new Document("$literal", 0));
        Document alerts = new Document("run_id", 1).append("symbol", 1).append("start", "$event_time")
            .append("end", "$event_time").append("indicator_count", new Document("$literal", 0))
            .append("alert_count", new Document("$literal", 1));
        return List.of(new Document("$match", match), new Document("$project", indicators),
            new Document("$unionWith", new Document("coll", "alerts").append("pipeline", List.of(
                new Document("$match", match), new Document("$project", alerts)))),
            new Document("$group", new Document("_id", "$run_id").append("symbols", new Document("$addToSet", "$symbol"))
                .append("start", new Document("$min", "$start")).append("end", new Document("$max", "$end"))
                .append("indicator_count", new Document("$sum", "$indicator_count"))
                .append("alert_count", new Document("$sum", "$alert_count"))),
            new Document("$sort", new Document("start", -1).append("_id", 1)),
            new Document("$skip", (long) page * limit), new Document("$limit", limit));
    }
}

