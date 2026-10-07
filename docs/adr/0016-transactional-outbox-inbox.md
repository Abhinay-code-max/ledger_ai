# ADR 0016: Transactional outbox and consumer inbox

Status: Accepted

State changes and outbox rows commit in one PostgreSQL transaction. Dispatch occurs only after
commit. A failed broker acknowledgement leaves the row pending or failed with bounded backoff;
successful acknowledgement records publication time. Publication after a broker success but
before database acknowledgement may duplicate delivery, so consumers atomically claim
`consumer_name + event_id` in the inbox before producing a side effect.

PostgreSQL remains authoritative. Redis loss cannot erase committed work. Poison payloads and
retry exhaustion use explicit dead-letter states; replay must be an authorized operational action,
not a row deletion.
