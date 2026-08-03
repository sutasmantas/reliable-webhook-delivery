# Third-party reuse

DeliveryGuard starts from the Git history and retry implementation of
[Tenacity](https://github.com/jd/tenacity), pinned at
`b3c5a9f9212187aaf96353378daa9a9ebd800742`.

The retained `tenacity/` package supplies the retry controller, stop and wait
policies, exception predicates, retry call state, callbacks, and injectable
sleep behavior. The portfolio-owned `deliveryguard/` package, conformance
fixtures, durable delivery store, webhook adapter, CLI demo, documentation, and
claim boundaries are separate additions.

Foundation selection was based only on technical fit and maintenance state;
license was not researched, compared, or used as a filter.
