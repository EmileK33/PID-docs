"""Drawing-lifecycle service layer (S2-B).

Houses the pure-logic services behind the drawings router: the drawing state
machine, the free-tier monthly counter, the hash-check gate, drawing creation,
and the upload-complete enqueue path. Routers stay thin; the load-bearing
contracts consumed by S2-H/I/J (``drawing_state_machine``,
``IngestJobPayload``) live here.
"""
