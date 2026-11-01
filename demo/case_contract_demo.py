#!/usr/bin/env python3
"""Synthetic software-contract demonstrator. No LLM, audio, network, or real data."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import copy
import json


class ContractError(ValueError):
    pass


class Forbidden(ContractError):
    pass


class SourceUnavailable(ContractError):
    pass


class AckLost(ContractError):
    pass


@dataclass(frozen=True)
class Fragment:
    fragment_id: str
    text: str
    modality: str = "text"
    # Mock anchors only. These are trusted adapter inputs, never model claims.
    anchor: str = "body"


@dataclass(frozen=True)
class Source:
    source_id: str
    version: int
    product_id: str
    customer_key: str | None
    episode_key: str | None
    expires_at: int
    fragments: tuple[Fragment, ...]

    @property
    def digest(self):
        payload = [(f.fragment_id, f.text, f.modality, f.anchor) for f in self.fragments]
        return sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


class ContractDemo:
    """Single-process in-memory state; not production authentication/storage."""
    labels = {"incident", "service_request", "feature_request", "usability", "unknown"}
    eligible = {"feature_request", "usability"}

    def __init__(self, now=100):
        self.now = now
        self.acl = {}  # Mutable permissions deliberately rechecked at every access.
        self.sources = {}
        self.analyses = {}
        self.topics = {}
        self.cache = {}
        self.index = {}
        self.outbox = {}
        self.receiver = {}  # Mock destination with idempotency key support.
        self.tombstones = {}  # Hashed source ID -> deleted version; blocks delayed replay.
        self.audit = []  # Metadata only; no quotes/prompts/source bodies.

    def grant(self, actor, products):
        self.acl[actor] = set(products)

    def _scope(self, actor, product):
        if product not in self.acl.get(actor, set()):
            raise Forbidden("Product scope denied")

    def _source(self, actor, source_id):
        source = self.sources.get(source_id)
        if source is None:
            raise SourceUnavailable("Source absent")
        self._scope(actor, source.product_id)
        if source.expires_at <= self.now:
            self.delete_source(source_id)
            raise SourceUnavailable("Source expired; derivatives purged")
        return source

    def add_topic(self, topic_id, product_id, title):
        if topic_id in self.topics:
            raise ContractError("Topic already exists")
        self.topics[topic_id] = dict(product_id=product_id, title=title, decision="new")

    def rename_topic(self, actor, topic_id, title):
        topic = self.topics[topic_id]
        self._scope(actor, topic["product_id"])
        topic["title"] = title
        self._invalidate_delivery(topic_id)

    def decide(self, actor, topic_id, decision):
        topic = self.topics[topic_id]
        self._scope(actor, topic["product_id"])
        if decision not in {"new", "accepted", "rejected", "planned", "implemented"}:
            raise ContractError("Unknown decision")
        topic["decision"] = decision
        self._invalidate_delivery(topic_id)

    def register_source(self, source):
        """Trusted adapter ingress, unavailable to a model. Update invalidates derivatives."""
        if source.expires_at <= self.now or type(source.version) is not int or source.version < 1:
            raise ContractError("Expired or invalid source")
        tombstone_key = sha256(source.source_id.encode()).hexdigest()
        if source.version <= self.tombstones.get(tombstone_key, 0):
            raise ContractError("Deleted source version cannot be resurrected by replay")
        fragment_ids = [f.fragment_id for f in source.fragments]
        if len(set(fragment_ids)) != len(fragment_ids):
            raise ContractError("Ambiguous fragment IDs")
        previous = self.sources.get(source.source_id)
        if previous:
            if source.product_id != previous.product_id:
                raise ContractError("Source cannot migrate product")
            if source.version < previous.version:
                raise ContractError("Out-of-order version")
            if source.version == previous.version:
                if source != previous:
                    raise ContractError("Same version must be immutable")
                return False
            self.delete_source(source.source_id)
        self.sources[source.source_id] = source
        self.cache[source.source_id] = tuple(f.text for f in source.fragments)
        self.index[source.source_id] = " ".join(f.text for f in source.fragments)
        self.audit.append(("source_registered", source.source_id, source.version))
        return True

    def analyze(self, actor, payload):
        """Validate a prepared model output. No semantics or model confidence is verified."""
        if set(payload) != {"source_id", "source_version", "pipeline_version", "items"}:
            raise ContractError("Unexpected/missing envelope fields")
        source = self._source(actor, payload["source_id"])
        if type(payload["source_version"]) is not int or source.version != payload["source_version"]:
            raise ContractError("Stale source version")
        if not isinstance(payload["pipeline_version"], str) or not payload["pipeline_version"]:
            raise ContractError("Missing pipeline version")
        if not isinstance(payload["items"], list) or not payload["items"]:
            raise ContractError("Nonempty items required")
        fragments = {f.fragment_id: f for f in source.fragments}
        validated = []
        for item in payload["items"]:
            if set(item) != {"label", "need", "topic_id", "evidence"}:
                raise ContractError("Unexpected/missing item fields")
            if item["label"] not in self.labels or not isinstance(item["need"], str):
                raise ContractError("Invalid label/need")
            topic_id = item["topic_id"]
            if topic_id is not None:
                topic = self.topics.get(topic_id)
                if not topic or topic["product_id"] != source.product_id:
                    raise Forbidden("Topic outside source scope")
                if item["label"] not in self.eligible:
                    raise ContractError("Incident/service/unknown cannot enter wish topic")
            if not isinstance(item["evidence"], list) or not item["evidence"]:
                raise ContractError("Evidence required")
            evidence = []
            for cite in item["evidence"]:
                if set(cite) != {"fragment_id", "start", "end", "quote"}:
                    raise ContractError("Unexpected/missing evidence fields")
                fragment = fragments.get(cite["fragment_id"])
                start, end = cite["start"], cite["end"]
                if fragment is None or type(start) is not int or type(end) is not int:
                    raise ContractError("Unknown fragment or invalid offsets")
                if not 0 <= start < end <= len(fragment.text):
                    raise ContractError("Invalid coordinate range")
                if fragment.text[start:end] != cite["quote"]:
                    raise ContractError("Quote does not match exact source span")
                evidence.append(dict(**cite, source_id=source.source_id,
                                     source_version=source.version, digest=source.digest,
                                     modality=fragment.modality, anchor=fragment.anchor))
            validated.append(dict(label=item["label"], need=item["need"],
                                  topic_id=topic_id, evidence=evidence))
        # Commit after validating the complete response: no partial write on invalid item.
        key = (source.source_id, source.version, payload["pipeline_version"])
        record = dict(product_id=source.product_id, items=validated)
        if key in self.analyses:
            if self.analyses[key] != record:
                raise ContractError("Idempotency conflict for same source/pipeline version")
            return False
        # A new pipeline version replaces active analysis, never doubles the same source.
        old_topics = {i["topic_id"] for k, a in self.analyses.items() if k[0] == source.source_id
                      for i in a["items"] if i["topic_id"] is not None}
        self.analyses = {k: a for k, a in self.analyses.items() if k[0] != source.source_id}
        self.analyses[key] = record
        for topic_id in old_topics | {i["topic_id"] for i in validated if i["topic_id"] is not None}:
            self._invalidate_delivery(topic_id)
        return True

    def card(self, actor, topic_id):
        topic = self.topics[topic_id]
        self._scope(actor, topic["product_id"])
        self.purge_expired()
        evidence, source_ids, episodes, customers = [], set(), set(), set()
        unknown_customers = 0
        for key, analysis in self.analyses.items():
            source = self.sources[key[0]]
            items = [i for i in analysis["items"] if i["topic_id"] == topic_id]
            if not items:
                continue
            self._scope(actor, source.product_id)
            source_ids.add(source.source_id)
            # episode_key must be a trusted canonical case/link ID, not a model guess.
            episodes.add((source.product_id, source.episode_key or "source:" + source.source_id))
            if source.customer_key:
                customers.add(source.customer_key)
            else:
                unknown_customers += 1
            evidence.extend(c for i in items for c in i["evidence"])
        return copy.deepcopy(dict(topic_id=topic_id, **topic, raw_sources=len(source_ids),
                    independent_episodes=len(episodes), known_customers=len(customers),
                    sources_with_unknown_customer=unknown_customers, evidence=evidence))

    def queue_card(self, actor, topic_id):
        payload = self.card(actor, topic_id)
        if not payload["evidence"]:
            raise ContractError("No live evidence; cannot publish")
        key = payload["product_id"] + ":" + topic_id
        self.outbox[key] = copy.deepcopy(payload)
        return key

    def deliver_once(self, actor, key, lose_ack=False):
        pending = self.outbox.get(key)
        if pending is None:
            return False
        # Permission and provenance may have changed since queueing.
        self._scope(actor, pending["product_id"])
        fresh = self.card(actor, pending["topic_id"])
        if not fresh["evidence"] or fresh != pending:
            self.outbox.pop(key, None)
            raise ContractError("Stale payload; regenerate before publication")
        # Mock receiver upsert is keyed by product/topic; no real external write.
        self.receiver[key] = copy.deepcopy(fresh)
        if lose_ack:
            raise AckLost("Mock: destination committed, acknowledgement lost")
        del self.outbox[key]
        return True

    def _invalidate_delivery(self, topic_id):
        for store in (self.outbox, self.receiver):
            for key in [k for k, card in store.items() if card["topic_id"] == topic_id]:
                del store[key]

    def delete_source(self, source_id):
        source = self.sources.get(source_id)
        if source:
            tombstone_key = sha256(source_id.encode()).hexdigest()
            self.tombstones[tombstone_key] = max(source.version, self.tombstones.get(tombstone_key, 0))
        affected = {i["topic_id"] for k, a in self.analyses.items() if k[0] == source_id
                    for i in a["items"] if i["topic_id"] is not None}
        self.sources.pop(source_id, None)
        self.cache.pop(source_id, None)
        self.index.pop(source_id, None)
        self.analyses = {k: a for k, a in self.analyses.items() if k[0] != source_id}
        for topic_id in affected:
            self._invalidate_delivery(topic_id)
        self.audit.append(("source_purged", source_id))

    def purge_expired(self):
        for source_id in [s.source_id for s in self.sources.values() if s.expires_at <= self.now]:
            self.delete_source(source_id)


def prepared_output(source, topic_id="csv", label="feature_request", need="Экспорт CSV"):
    """Hand-authored output fixture, explicitly NOT an LLM result."""
    f = source.fragments[0]
    return dict(source_id=source.source_id, source_version=source.version,
                pipeline_version="fixture-v1", items=[dict(label=label, need=need,
                topic_id=topic_id, evidence=[dict(fragment_id=f.fragment_id,
                start=0, end=len(f.text), quote=f.text)])])


def run_demo():
    demo = ContractDemo()
    demo.grant("owner", {"fuel"})
    demo.add_topic("csv", "fuel", "Экспорт CSV")
    fixtures = (
        Source("ticket-1", 1, "fuel", "client-a", "case-1", 1000,
               (Fragment("body", "Хочу выгрузить заказы в CSV."),)),
        Source("call-1", 1, "fuel", "client-a", "case-1", 1000,
               (Fragment("segment-1", "Хочу выгрузить заказы в CSV.", "audio", "00:30–00:45"),)),
        Source("ticket-2", 1, "fuel", "client-b", "case-2", 1000,
               (Fragment("body", "Хочу выгрузить заказы в CSV."),)),
    )
    for source in fixtures:
        demo.register_source(source)
        demo.analyze("owner", prepared_output(source))
    demo.decide("owner", "csv", "accepted")
    before = demo.card("owner", "csv")
    key = demo.queue_card("owner", "csv")
    try:
        demo.deliver_once("owner", key, lose_ack=True)
    except AckLost:
        pass
    demo.deliver_once("owner", key)
    deliveries = len(demo.receiver)
    demo.delete_source("call-1")
    after = demo.card("owner", "csv")
    return {"disclaimer": "Синтетические данные; вызовов Qwen/ASR/VL и внешних API нет.",
            "before_delete": before, "mock_destination_cards_after_retry": deliveries,
            "after_delete": after,
            "limits": "Проверяется программный контракт, не смысл/точность моделей."}


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2))
