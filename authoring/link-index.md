# Link index (generated from assets/js/catalog.js)

Every page on the site, by course. Link with a path relative to the page you are writing, e.g. from evals/chapters/x.html to ../../reliability/chapters/06-tracing.html, or within a course ../chapters/02-tool-loop.html. Cross-course ids for catalog `related` fields are written course-id:chapter-id (only the coordinator edits the catalog).

## Course 0 · Networking from Zero  (id "net", folder networking/)

Part 0: Orientation
- networking/chapters/00-start-here.html · ch 00 · intro · Start Here: What a network is, and the journey of a single message.
Part 1: Foundations: Moving Bits
- networking/chapters/01-bits-and-signals.html · ch 01 · deep · Bits, Bytes & Signals: Binary, wires, light, radio, and the crucial difference between bandwidth and latency.
- networking/chapters/02-local-networks.html · ch 02 · core · Local Networks & Ethernet: Frames, MAC addresses, switches and Wi-Fi: talking to the computer next to you.
- networking/chapters/03-layers.html · ch 03 · deep · Layers & Encapsulation: Envelopes inside envelopes: the single most useful mental model in networking.
Part 2: The Internet Layer
- networking/chapters/04-ip-addresses.html · ch 04 · deep · IP Addresses & Subnets: Addresses, binary, CIDR, private ranges, NAT and a peek at IPv6.
- networking/chapters/05-routing.html · ch 05 · deep · Routing: Routers, routing tables, hops and how the Internet stitches itself together.
- networking/chapters/06-arp-dhcp-icmp.html · ch 06 · intro · The Glue: ARP, DHCP & ICMP: Small helper protocols that make everything else work.
Part 3: Transport
- networking/chapters/07-ports-udp.html · ch 07 · core · Ports, Sockets & UDP: Which program gets the data, and the simplest way to send it.
- networking/chapters/08-tcp.html · ch 08 · deep · TCP Deep Dive: Handshakes, sequence numbers, retransmission, flow and congestion control.
Part 4: Applications
- networking/chapters/09-dns.html · ch 09 · deep · DNS: The Internet's Phonebook: Turning names into addresses with a giant, cached, distributed database.
- networking/chapters/10-http.html · ch 10 · deep · HTTP & the Web: Requests, responses, status codes, and what happens when you type a URL.
- networking/chapters/11-tls.html · ch 11 · core · TLS & Security Basics: Encryption, keys, certificates and the padlock in your browser.
- networking/chapters/12-apis.html · ch 12 · core · How Programs Talk: Sockets & APIs: Client/server, REST, RPC, WebSockets and serialization.
Part 5: Networks at Scale
- networking/chapters/13-performance.html · ch 13 · deep · Latency, Throughput & Performance: Numbers every engineer should know, and why the slowest request matters most.
- networking/chapters/14-load-balancers.html · ch 14 · core · Proxies, Load Balancers & CDNs: The machines in the middle that make big websites possible.
Part 6: Toward Distributed Systems
- networking/chapters/15-why-distribute.html · ch 15 · deep · Why Distribute? Partial Failure: Why we use many machines, and the 8 lies we tell ourselves about networks.
- networking/chapters/16-failure.html · ch 16 · deep · Failure, Timeouts & Retries: Slow or dead? Retries, idempotency, delivery guarantees and the Two Generals.
- networking/chapters/17-time.html · ch 17 · deep · Time, Clocks & Ordering: Why clocks lie, and how Lamport and vector clocks restore order.
- networking/chapters/18-replication.html · ch 18 · deep · Replication & Consistency: Copies of data, quorums, consistency models and the CAP theorem.
- networking/chapters/19-partitioning.html · ch 19 · core · Partitioning & Consistent Hashing: Splitting data across machines without reshuffling everything.
- networking/chapters/20-consensus.html · ch 20 · deep · Consensus & Raft: How a group of unreliable machines agrees on anything at all.
- networking/chapters/21-where-next.html · ch 21 · intro · Patterns & Where to Go Next: Queues, logs, sagas, circuit breakers, and a reading list.
Part 7: Extensions
- networking/chapters/22-cloud-networking.html · ch 22 · core · Cloud Networking: VPCs, subnets, route tables, security groups, NAT and private endpoints: the network you rent from a cloud provider.
Labs:
- networking/labs/lab-01-sockets.html · L1 (after Part 3) · Sockets & a Chat Server: UDP echo, then a multi-client TCP chat server. Framing, ports and byte streams in practice.
- networking/labs/lab-02-reliable-udp.html · L2 (after Part 3) · Reliable Delivery over UDP: Rebuild TCP's core: sequence numbers, ACKs, timeouts and a sliding window over a lossy link.
- networking/labs/lab-03-dns-resolver.html · L3 (after Part 4) · A DNS Resolver from Scratch: Build DNS packets byte by byte, ask the root servers and follow referrals with a TTL cache.
- networking/labs/lab-04-http-server.html · L4 (after Part 4) · An HTTP Server from Scratch: Parse requests, serve files, send status codes and headers, and support keep-alive.
- networking/labs/lab-05-kv-store.html · L5 (after Part 6) · A Replicated Key-Value Store: Three nodes, quorum reads and writes, stale reads, retries with backoff and idempotency keys.
- networking/labs/lab-06-raft.html · L6 (after Part 6) · Toy Raft: Leader election and log replication in a deterministic simulation you can partition.
Cases:
- networking/cases/case-01-anycast.html · C1 · Anycast: One Address, Many Places [Anycast routing]: How one IP address can live in hundreds of cities, and BGP sends you to the nearest.
- networking/cases/case-02-isp-caches.html · C2 · Caches Inside Your ISP [Push content to the edge]: Why streaming services put their servers inside other companies' networks.
- networking/cases/case-03-dns-steering.html · C3 · Steering Traffic with DNS [DNS-based load balancing]: GeoDNS, short TTLs and failover, and why DNS is a coarse steering wheel.
- networking/cases/case-04-nat-traversal.html · C4 · Punching Through NAT [NAT traversal]: How two devices that are both behind NAT manage to talk directly: STUN, TURN, ICE.
- networking/cases/case-05-persistent-connections.html · C5 · Millions of Open Connections [Connection gateways & fan-out]: How chat apps keep a live connection to every user and deliver messages instantly.
- networking/cases/case-06-facebook-2021.html · C6 · When the Map Disappears: Facebook, 2021 [Control-plane dependencies]: A routine command withdrew Facebook's routes, its DNS vanished, and so did the tools to fix it.
- networking/cases/case-07-s3-2017.html · C7 · Small Mistake, Big Blast Radius: S3, 2017 [Blast radius & cells]: One mistyped input, a cold restart, and a lesson in containing failures.
- networking/cases/case-08-retry-storms.html · C8 · Retry Storms & Metastable Failures [Load shedding & backoff]: When the system stays down after the trigger is gone, and how to stop feeding the fire.
- networking/cases/case-09-dynamo.html · C9 · Dynamo: The Cart That Always Says Yes [Leaderless replication]: Amazon's always-writable store: consistent hashing, sloppy quorums and vector clocks.
- networking/cases/case-10-ordering-at-scale.html · C10 · Ordering at Scale: Spanner & the Log [Global order from clocks & logs]: Two ways to give the whole world one order of events: trusted clocks and a shared log.
Toolbox (networking/toolbox.html#id):
- #wireshark · Wireshark · chapters 03,07,08,09,10,11: See every packet and every layer of every header, decoded. The single best way to make this course real.
- #tcpdump · tcpdump · chapters 07,08,09: Wireshark's command-line cousin: capture packets in a terminal or on a remote server.
- #ping-mtr · ping, traceroute & mtr · chapters 05,06,13,22: Measure round-trip time and watch the routers your packets cross.
- #dig · dig · chapters 09,22: Ask DNS servers anything and read their full answers, referrals and TTLs.
- #curl · curl · chapters 10,11,12: Speak HTTP by hand and see headers, redirects, TLS and timing.
- #nc · netcat (nc) · chapters 07,08,12: Open raw TCP or UDP connections and type bytes straight into a socket.
- #openssl · openssl s_client · chapters 11: Do a TLS handshake by hand and inspect a server's certificate chain.
- #ss-lsof · ss, netstat & lsof · chapters 07,08,14: List open sockets, listening ports and connection states on your machine.
- #iperf3 · iperf3 · chapters 01,13: Measure real throughput between two machines, and see bandwidth vs latency.

## Course 1 · How Programs Run  (id "sys", folder systems/)

Part 0: Orientation
- systems/chapters/00-start-here.html · ch 00 · intro · Start Here: One request's journey through a single machine, and the map of this course.
Part 1: The Machine
- systems/chapters/01-cpu.html · ch 01 · core · CPUs & Instructions: What a program really is, how a CPU runs it, and what cores and clock speed mean.
- systems/chapters/02-memory-hierarchy.html · ch 02 · deep · The Memory Hierarchy: Registers, caches, RAM, disk: the ladder of speeds, and why locality rules performance.
- systems/chapters/03-stack-heap.html · ch 03 · core · Stack, Heap & Garbage Collection: Where a running program keeps its data, and who cleans up after it.
Part 2: The Operating System
- systems/chapters/04-kernel-syscalls.html · ch 04 · deep · The Kernel & System Calls: The referee between programs and hardware, and the doorway every program must knock on.
- systems/chapters/05-processes.html · ch 05 · deep · Processes: fork, exec, wait, signals and exit codes: how programs are born, run and die.
- systems/chapters/06-virtual-memory.html · ch 06 · deep · Virtual Memory: Every process gets its own private universe of addresses. Pages, page faults and the TLB.
- systems/chapters/07-scheduling.html · ch 07 · intro · Scheduling & Context Switches: How one CPU core takes turns between hundreds of programs, and what switching costs.
- systems/chapters/08-files.html · ch 08 · core · Files & File Descriptors: Inodes, directories, permissions, and why a socket is "just a file" too.
- systems/chapters/09-durability.html · ch 09 · deep · Durability: Written Is Not Saved: The page cache, fsync, atomic rename and journaling: what survives when the power goes out.
Part 3: Concurrency
- systems/chapters/10-threads.html · ch 10 · core · Threads: Several flows of execution sharing one memory, and how they differ from processes.
- systems/chapters/11-race-conditions.html · ch 11 · deep · Race Conditions: Interleavings, lost updates and check-then-act: why counter += 1 is not one step.
- systems/chapters/12-locks.html · ch 12 · deep · Locks, Atomics & Condition Variables: Mutexes, compare-and-swap, semaphores and waiting politely for something to happen.
- systems/chapters/13-deadlock.html · ch 13 · core · Deadlock, Livelock & Starvation: When threads wait for each other forever, and the simple rules that prevent it.
- systems/chapters/14-queues-backpressure.html · ch 14 · deep · Queues, Thread Pools & Backpressure: Bounded queues, worker pools, Little's law and saying "not now" before you fall over.
Part 4: Talking to the World
- systems/chapters/15-blocking-io.html · ch 15 · core · Blocking vs Non-blocking I/O: What happens when a program waits for the network or the disk, and how to stop waiting.
- systems/chapters/16-event-loops.html · ch 16 · deep · Event Loops: select, poll, epoll and kqueue: one thread juggling thousands of connections.
- systems/chapters/17-async-await.html · ch 17 · core · Async/Await & Coroutines: Futures, coroutines and the golden rule: never block the loop.
- systems/chapters/18-concurrency-models.html · ch 18 · core · Concurrency Models Compared: Threads, events, actors and channels, and how real servers mix them.
Part 5: Isolation
- systems/chapters/19-containers-vms.html · ch 19 · core · Containers & Virtual Machines: Hypervisors, namespaces and cgroups: what Docker actually does.
- systems/chapters/20-where-next.html · ch 20 · intro · Where Next: On to Data Systems: What you can now explain, and how it sets you up for databases.
Part 6: Extensions
- systems/chapters/21-parallelism-gpus.html · ch 21 · core · Parallelism, SIMD & GPUs: Amdahl's law, vector instructions, GPUs and memory bandwidth: why machine learning runs on accelerators.
- systems/chapters/22-performance-engineering.html · ch 22 · deep · Performance Engineering: A method for making programs faster: measure, profile on- and off-CPU, read flame graphs and benchmark honestly.
Labs:
- systems/labs/lab-01-shell.html · L1 (after Part 2) · A Mini Shell: fork, exec and wait, then pipes, redirection and Ctrl-C. Build the program you type into.
- systems/labs/lab-02-crash-safe-log.html · L2 (after Part 2) · Crash-Safe Storage: An append-only log with checksums and fsync that recovers cleanly when killed mid-write.
- systems/labs/lab-03-races-locks.html · L3 (after Part 3) · Races & Locks: Reproduce a lost update, fix it, cause a deadlock, fix that, and build a blocking queue.
- systems/labs/lab-04-thread-pool.html · L4 (after Part 3) · A Thread Pool with Backpressure: Workers, futures, a bounded queue and rejection policies, measured under load.
- systems/labs/lab-05-event-loop.html · L5 (after Part 4) · Your Own Event Loop: Callbacks and timers on selectors, then coroutines, serving a thousand connections on one thread.
Cases:
- systems/cases/case-01-fsyncgate.html · C1 · fsyncgate: When fsync Fails [Durability lies]: PostgreSQL trusted that a failed fsync could simply be retried. The kernel disagreed.
- systems/cases/case-02-pathfinder.html · C2 · Priority Inversion on Mars [Priority inversion]: A spacecraft kept rebooting itself on Mars because a low-priority task held a lock.
- systems/cases/case-03-leap-second.html · C3 · The Leap Second That Broke DNS [Wall clock vs monotonic clock]: Time went backwards for one second, and a calculation that "could never be negative" was.
- systems/cases/case-04-c10k-nginx.html · C4 · Ten Thousand Connections: nginx & C10k [Event-driven servers]: Why one thread per connection stopped scaling, and the event-driven design that replaced it.
- systems/cases/case-05-redis.html · C5 · Redis: One Thread, Very Fast [Single-threaded event loop]: How a database serves huge request rates on a single thread, and where that design hurts.
- systems/cases/case-06-discord-gc.html · C6 · Discord & the Garbage Collector [GC pauses & tail latency]: Periodic latency spikes, traced to garbage collection, and a rewrite in a language without one.
- systems/cases/case-07-cloudflare-regex.html · C7 · One Regex, Every CPU: Cloudflare 2019 [CPU exhaustion & isolation]: A single regular expression consumed all CPU on machines worldwide. Why, and the safeguards since.
- systems/cases/case-08-borg.html · C8 · Borg: Containers at Google Scale [Isolation & bin-packing]: How Google packs many jobs onto shared machines, and the ideas that became Kubernetes.
Studios:
- systems/studios/studio-01-10k-connections.html · S1 (after Part 4) · Serve 10,000 Connections on One Machine: Threads or an event loop? Memory per connection, file-descriptor limits and where it breaks.
- systems/studios/studio-02-log-shipper.html · S2 (after Part 4) · A Log Shipper That Never Loses a Line: Batching, fsync policy, a disk spool and backpressure, from crash to recovery.
Toolbox (systems/toolbox.html#id):
- #top-htop · top & htop · chapters 05,07,10: Watch processes, threads, CPU and memory live.
- #lsof · lsof · chapters 08,15: See every file, pipe and socket a process has open.
- #strace · strace · chapters 04,08,16: Watch every system call a program makes, as it makes it.
- #proc · The /proc file system · chapters 05,06,08: Read the kernel's view of any process: memory maps, open files, limits.
- #vmstat · vm_stat, vmstat & iostat · chapters 06,09: Memory pressure, paging and disk activity, system-wide.
- #hyperfine · hyperfine · chapters 01,02,22: Benchmark commands properly: warm-ups, repeated runs and statistics.
- #py-spy · py-spy · chapters 03,10,17,22: Sample a running Python program and see where its time goes, without changing it.
- #perf · perf & flame graphs · chapters 01,02,07,22,21: Profile anything on Linux, down to cache misses, and draw it as a flame graph.
- #bpftrace · bpftrace · chapters 04,09: Ask the running kernel questions with one-liners (advanced, but magical).
- #unshare · unshare & Docker · chapters 19: Build a container by hand from namespaces, then compare with Docker.

## Course 2 · Data Systems  (id "data", folder data/)

Part 0: Orientation
- data/chapters/00-start-here.html · ch 00 · intro · Start Here: The life of one query, from SQL text to bytes on disk and back.
Part 1: Modelling Data
- data/chapters/01-data-models.html · ch 01 · core · Data Models: Relational, document, key-value, graph and wide-column: different shapes for different questions.
- data/chapters/02-sql-relational.html · ch 02 · core · SQL & the Relational Model: Tables, keys, joins and normalisation, and why SQL has lasted fifty years.
- data/chapters/03-encoding.html · ch 03 · core · Encoding & Schema Evolution: JSON, Protobuf and Avro, and changing your data's shape without breaking anyone.
Part 2: Storage Engines
- data/chapters/04-log-hash-index.html · ch 04 · deep · The Simplest Database: a Log: An append-only file plus an in-memory hash index, and the ideas every engine reuses.
- data/chapters/05-lsm-trees.html · ch 05 · deep · LSM Trees & SSTables: Memtables, sorted files, compaction and Bloom filters: storage built for fast writes.
- data/chapters/06-b-trees.html · ch 06 · deep · B-Trees: Pages, splits, the buffer pool and the WAL: the structure behind most SQL databases.
- data/chapters/07-indexes.html · ch 07 · deep · Indexes: Secondary, composite and covering indexes, and why the wrong index is worse than none.
- data/chapters/08-query-execution.html · ch 08 · core · Query Execution & Planning: Scans, joins and the planner's guesses: reading EXPLAIN like a pro.
- data/chapters/09-column-stores.html · ch 09 · core · Column Stores & Analytics: OLTP vs OLAP, columnar layout, compression and the data warehouse.
Part 3: Transactions
- data/chapters/10-acid.html · ch 10 · deep · Transactions & ACID: What atomicity, consistency, isolation and durability really promise, and what they don't.
- data/chapters/11-isolation.html · ch 11 · deep · Isolation Levels & Anomalies: Dirty reads, lost updates, write skew and phantoms, and which isolation level stops which.
- data/chapters/12-mvcc-locking.html · ch 12 · deep · Implementing Isolation: 2PL, MVCC & SSI: Locks versus versions: how databases actually keep transactions apart.
- data/chapters/13-crash-recovery.html · ch 13 · core · Crash Recovery: Write-ahead logs, checkpoints and redo/undo: coming back from a crash with nothing lost.
Part 4: Data at Scale
- data/chapters/14-caching.html · ch 14 · deep · Caching: Cache-aside, write-through, invalidation, TTLs, stampedes and hot keys.
- data/chapters/15-replication-practice.html · ch 15 · deep · Replication in Practice: Leaders, followers, replication lag and its anomalies, and failing over without losing data.
- data/chapters/16-sharding.html · ch 16 · core · Sharding in Practice: Choosing a shard key, hot spots, cross-shard queries and rebalancing.
- data/chapters/17-specialised-stores.html · ch 17 · intro · Search & Specialised Stores: Inverted indexes, time-series and vector databases, and when to reach for them.
Part 5: Data in Motion
- data/chapters/18-batch.html · ch 18 · core · Batch Processing: From Unix pipes to MapReduce and dataflow engines: processing all the data at once.
- data/chapters/19-streams-cdc.html · ch 19 · deep · Streams, Logs & Change Data Capture: Event logs, consumers, CDC and the outbox pattern: keeping many systems in sync.
- data/chapters/20-choosing.html · ch 20 · intro · Choosing a Database & Where Next: A practical way to pick storage for a workload, and the road to architecture.
Part 6: Extensions
- data/chapters/21-data-platforms.html · ch 21 · core · Data Platforms: Warehouses, Lakehouses & Pipelines: Open table formats, ELT, orchestration, data quality and lineage: how analytics data is moved and trusted.
Labs:
- data/labs/lab-01-bitcask.html · L1 (after Part 2) · A Log-Structured Key-Value Store: An append-only log with an in-memory hash index, crash recovery and compaction.
- data/labs/lab-02-lsm.html · L2 (after Part 2) · An LSM Tree: Memtable, SSTable flushes, merge compaction and a Bloom filter that skips files.
- data/labs/lab-03-btree.html · L3 (after Part 2) · A B-Tree: Search, insert with node splits and range scans, then count the pages you touch.
- data/labs/lab-04-slow-query.html · L4 (after Part 2) · Make a Slow Query Fast: SQLite, a million rows and EXPLAIN QUERY PLAN: indexes, covering indexes and query rewrites.
- data/labs/lab-05-mvcc.html · L5 (after Part 3) · Snapshot Isolation from Scratch: A multi-version store with snapshots and write conflicts, then catch write skew.
- data/labs/lab-06-outbox-cdc.html · L6 (after Part 5) · The Outbox & Change Data Capture: Keep a cache and a search index in sync with SQLite using an outbox and idempotent consumers.
Cases:
- data/cases/case-01-github-failover.html · C1 · 43 Seconds That Took a Day: GitHub, 2018 [Failover & split brain]: A brief network partition, an automatic database failover, and writes in two data centers.
- data/cases/case-02-discord-messages.html · C2 · Storing Trillions of Messages: Discord [Partition keys & hot spots]: From MongoDB to Cassandra to ScyllaDB, and the hot partitions that shaped each move.
- data/cases/case-03-memcache-facebook.html · C3 · Scaling Memcache at Facebook [Look-aside caching at scale]: Leases against stampedes and stale sets, regions and invalidation through the database log.
- data/cases/case-04-uber-postgres.html · C4 · Why Uber Moved from Postgres to MySQL [Storage-engine trade-offs]: Write amplification, MVCC and physical replication: how engine internals drove a migration.
- data/cases/case-05-gitlab-2017.html · C5 · The Backups That Weren't: GitLab, 2017 [Backups you have tested]: A tired engineer, the wrong server, and backup methods that did not work when they were needed.
- data/cases/case-06-figma-sharding.html · C6 · Sharding Postgres at Figma [Horizontal sharding]: From one database to vertical partitions to horizontal shards behind a query proxy.
- data/cases/case-07-stripe-migrations.html · C7 · Online Migrations at Stripe [Dual writes & backfills]: Moving live data to a new model in four phases without downtime.
- data/cases/case-08-aurora.html · C8 · Aurora: The Log Is the Database [Disaggregated storage]: Amazon's database that ships only redo log records to storage, and why that changes everything.
Studios:
- data/studios/studio-01-url-shortener.html · S1 (after Part 4) · Design a URL Shortener's Storage: Key generation, the read path, caching and sharding for a billion short links.
- data/studios/studio-02-ledger.html · S2 (after Part 3) · Design a Payments Ledger: Balances that are never wrong: double-entry, isolation, idempotency and audits.
Toolbox (data/toolbox.html#id):
- #sqlite · sqlite3 · chapters 02,07,08,10: A complete SQL database in one file, built into Python and macOS. Your everyday lab bench.
- #postgres · PostgreSQL & psql · chapters 02,08,11,12,15: The open-source workhorse: EXPLAIN ANALYZE, isolation levels and replication you can poke.
- #explain · EXPLAIN & EXPLAIN ANALYZE · chapters 07,08: Ask the planner what it will do, and what it actually did.
- #redis · redis-cli · chapters 14,19: Talk to an in-memory key-value store: TTLs, eviction and streams.
- #duckdb · DuckDB · chapters 09,18,21: An in-process column store: run analytics over CSV and Parquet files in milliseconds.
- #pgbench · pgbench · chapters 10,13: Benchmark Postgres and watch fsync and group commit change throughput.
- #jq · jq · chapters 03,19: Slice and reshape JSON on the command line.

## Course 3 · Software Architecture & Design  (id "arch", folder architecture/)

Part 0: Orientation
- architecture/chapters/00-start-here.html · ch 00 · intro · Start Here: What software architecture is, who does it, and how this course builds on the first three.
Part 1: Managing Complexity
- architecture/chapters/01-complexity.html · ch 01 · deep · Complexity & Why Software Rots: Change amplification, cognitive load and unknown unknowns, and tactical versus strategic programming.
- architecture/chapters/02-modules-coupling.html · ch 02 · deep · Modules, Coupling & Cohesion: Deep modules, information hiding, and the kinds of coupling that make change expensive.
- architecture/chapters/03-abstractions.html · ch 03 · core · Abstractions & Interfaces: Designing interfaces, contracts and errors, and noticing when abstractions leak.
- architecture/chapters/04-design-patterns.html · ch 04 · core · Design Patterns That Matter: Strategy, adapter, facade, observer, decorator and dependency injection, and when not to use them.
Part 2: Structuring an Application
- architecture/chapters/05-hexagonal.html · ch 05 · deep · Layers, Hexagonal & Clean Architecture: Keeping business rules independent of databases, frameworks and the web: the dependency rule.
- architecture/chapters/06-ddd.html · ch 06 · core · Domain-Driven Design Essentials: Ubiquitous language, bounded contexts, entities, value objects and aggregates.
- architecture/chapters/07-testability.html · ch 07 · core · Testability as Architecture: Seams, fakes and the test pyramid: designs that are easy to test are easy to change.
- architecture/chapters/08-cross-cutting.html · ch 08 · intro · Cross-Cutting Concerns: Configuration, errors, logging, metrics and security: things every module touches.
Part 3: APIs & Contracts
- architecture/chapters/09-api-design.html · ch 09 · deep · API Design: Resources, verbs, errors, pagination, idempotency keys, and REST versus RPC versus GraphQL.
- architecture/chapters/10-evolving-contracts.html · ch 10 · core · Evolving Contracts & Versioning: Compatibility rules, Hyrum's law, deprecation and versioning strategies.
Part 4: Monolith to Services
- architecture/chapters/11-monolith-microservices.html · ch 11 · deep · Monoliths, Modular Monoliths & Microservices: The real trade-offs, Conway's law, and why most teams should start with a modular monolith.
- architecture/chapters/12-service-boundaries.html · ch 12 · core · Drawing Service Boundaries: Data ownership, database-per-service and the distributed-monolith trap.
- architecture/chapters/13-sync-async.html · ch 13 · core · Sync vs Async Communication: Request/response versus messaging, temporal coupling and the cost of every network hop.
Part 5: Events & Workflows
- architecture/chapters/14-event-driven.html · ch 14 · deep · Event-Driven Architecture: Events versus commands, notification versus state transfer, and choreography's hidden costs.
- architecture/chapters/15-sagas.html · ch 15 · deep · Sagas & Distributed Workflows: Business transactions across services with compensations instead of rollbacks.
- architecture/chapters/16-cqrs-event-sourcing.html · ch 16 · core · CQRS & Event Sourcing: Separate read and write models, and storing every change as an event.
Part 6: Resilience & Evolution
- architecture/chapters/17-resilience.html · ch 17 · deep · Resilience Patterns: Timeouts, retries, circuit breakers, bulkheads, rate limits and graceful degradation.
- architecture/chapters/18-evolving-safely.html · ch 18 · core · Evolving Systems Safely: Strangler fig, branch by abstraction, feature flags, expand/contract and canaries.
- architecture/chapters/19-documenting-decisions.html · ch 19 · core · Documenting & Deciding: Architecture decision records, design docs, C4 diagrams and trade-off analysis.
- architecture/chapters/20-where-next.html · ch 20 · intro · Where Next: On to Distributed Systems: What you can now design, and the hard distributed problems still ahead.
Part 7: Extensions
- architecture/chapters/21-engineering-practice.html · ch 21 · core · Engineering Practice at Scale: Code review, continuous integration, trunk-based development, monorepos and build systems: how many engineers change one codebase safely.
Labs:
- architecture/labs/lab-01-hexagonal.html · L1 (after Part 2) · Refactor to Hexagonal: Untangle a script that mixes SQL, HTTP and business rules into a core with ports and adapters.
- architecture/labs/lab-02-api.html · L2 (after Part 3) · An Idempotent, Paginated, Versioned API: A small WSGI API with idempotency keys, cursor pagination, consistent errors and a v2 that breaks nobody.
- architecture/labs/lab-03-module-boundaries.html · L3 (after Part 4) · Enforce Module Boundaries: Write an import checker, then split a monolith into modules that only talk through public interfaces.
- architecture/labs/lab-04-saga.html · L4 (after Part 5) · A Saga Orchestrator: Order, payment, stock and shipping with compensations, idempotent steps and crash-safe resume.
- architecture/labs/lab-05-event-sourcing.html · L5 (after Part 5) · Event Sourcing & CQRS: An event store, aggregates rebuilt from events, snapshots and projections for queries.
- architecture/labs/lab-06-resilience.html · L6 (after Part 6) · A Resilience Toolkit: Timeouts, retries with jitter, a circuit breaker and a bulkhead, tested against a flaky fake.
Cases:
- architecture/cases/case-01-prime-video.html · C1 · Prime Video: Back to a Monolith [Right-sizing services]: A monitoring service rebuilt from distributed components into one process, and why that was the right call.
- architecture/cases/case-02-segment.html · C2 · Goodbye Microservices: Segment [When services multiply pain]: Over a hundred destination services, shared libraries and queues, and the decision to consolidate.
- architecture/cases/case-03-shopify.html · C3 · Shopify's Modular Monolith [Modular monolith]: Keeping one huge codebase healthy with components, boundaries and tooling instead of services.
- architecture/cases/case-04-netflix-hystrix.html · C4 · Netflix, Hystrix & Chaos [Circuit breakers & bulkheads]: Isolating failing dependencies so one slow service cannot take down everything else.
- architecture/cases/case-05-stripe-versioning.html · C5 · Stripe's API Versioning [Versioned contracts]: Keeping years of integrations working while the API keeps changing underneath.
- architecture/cases/case-06-uber-doma.html · C6 · Uber's Domain-Oriented Microservices [Domains & layers of services]: Grouping thousands of services into domains with gateways and extension points.
- architecture/cases/case-07-knight-capital.html · C7 · Knight Capital: 45 Minutes, $460 Million [Dead code & unsafe deploys]: A partial deployment, a repurposed flag and old code that came back to life.
- architecture/cases/case-08-lmax.html · C8 · LMAX: One Thread, Millions of Orders [In-memory event sourcing]: A trading exchange built on a single-threaded business core fed by an input event log.
Studios:
- architecture/studios/studio-01-food-delivery.html · S1 (after Part 5) · Design Food Delivery's Service Boundaries: Contexts, data ownership, sync versus async calls and the order saga for a delivery app.
- architecture/studios/studio-02-notifications.html · S2 (after Part 6) · Design a Notification Service: Many channels, preferences, templates, rate limits, retries and never notifying twice.
Toolbox (architecture/toolbox.html#id):
- #mermaid · Mermaid (diagrams as code) · chapters 00,19: Write architecture and sequence diagrams as text that lives next to your code.
- #openapi · OpenAPI · chapters 09,10: Describe an HTTP API in a machine-readable contract, then generate docs and checks from it.
- #import-graph · Import graphs & boundary checkers · chapters 02,05,11,21: See and enforce which modules may depend on which.
- #unittest · unittest & doubles · chapters 07,05,21: Python's built-in test framework, fakes and mocks: the tools of testable design.
- #adr · Architecture decision records · chapters 19: A tiny, durable format for writing down why a decision was made.
- #load · HTTP load generators · chapters 13,17: Push traffic at a service and watch timeouts, retries and circuit breakers behave.

## Course 4 · Distributed Systems, Deep  (id "dist", folder distributed/)

Part 0: Orientation
- distributed/chapters/00-start-here.html · ch 00 · intro · Start Here: What you already know from networking Part 6, what is still hard, and how this course goes deeper.
Part 1: Models & Failure
- distributed/chapters/01-system-models.html · ch 01 · deep · System Models: Time, Failure & Correctness: Synchronous, asynchronous and partially synchronous systems; crash, omission and Byzantine faults; safety and liveness.
- distributed/chapters/02-impossibility.html · ch 02 · core · What Is Impossible: FLP, CAP & PACELC: Why consensus cannot be guaranteed in a purely asynchronous system, what CAP actually says, and the latency trade-off it leaves out.
- distributed/chapters/03-failure-detection.html · ch 03 · deep · Failure Detection, Membership & Gossip: Heartbeats, phi-accrual detectors, SWIM and epidemic gossip: knowing who is alive without asking everyone.
- distributed/chapters/04-leases-fencing.html · ch 04 · deep · Leases, Locks & Fencing Tokens: Why a distributed lock is never quite a lock, how leases expire, and how fencing tokens make pauses safe.
Part 2: Consistency
- distributed/chapters/05-consistency-models.html · ch 05 · deep · Consistency Models, Precisely: Histories, linearizability, sequential and serializable consistency, and how to tell which one a system gives you.
- distributed/chapters/06-causal-session.html · ch 06 · core · Causal Consistency & Session Guarantees: Read-your-writes, monotonic reads, causal order, and the strongest model that never blocks on a partition.
- distributed/chapters/07-time-revisited.html · ch 07 · core · Time Revisited: HLCs & TrueTime: Hybrid logical clocks, bounded clock uncertainty, commit wait, and when physical time can be trusted.
Part 3: Consensus
- distributed/chapters/08-consensus-smr.html · ch 08 · deep · Consensus & Replicated State Machines: The consensus problem, quorum intersection, total-order broadcast, and why one log can run any service.
- distributed/chapters/09-paxos.html · ch 09 · deep · Paxos, Step by Step: Single-decree Paxos, why each phase exists, duelling proposers, and Multi-Paxos.
- distributed/chapters/10-raft-deep.html · ch 10 · deep · Raft in Depth: The commitment rule's subtle case, membership changes, snapshots, linearizable reads and pre-vote.
- distributed/chapters/11-coordination-services.html · ch 11 · core · Coordination Services: ZooKeeper & etcd: Watches, ephemeral nodes, leader-election recipes, and what does not belong in a coordination service.
- distributed/chapters/12-byzantine.html · ch 12 · intro · Byzantine Faults & Beyond: When nodes may lie: the 3f+1 bound, PBFT in outline, and where blockchains fit.
Part 4: Transactions Across Machines
- distributed/chapters/13-atomic-commit.html · ch 13 · deep · Atomic Commit: 2PC & Its Limits: Two-phase commit, the blocking problem, presumed abort, and putting the coordinator on consensus.
- distributed/chapters/14-distributed-transactions.html · ch 14 · deep · Distributed Transactions in Practice: Percolator, Spanner and Calvin: three designs for serializable transactions across machines.
- distributed/chapters/15-crdts.html · ch 15 · deep · CRDTs: Data That Merges Itself: Join semilattices, state- and operation-based CRDTs, counters, sets, registers and collaborative text.
- distributed/chapters/16-coordination-avoidance.html · ch 16 · core · Coordination Avoidance: Which invariants need coordination, the CALM theorem, escrow and bounded counters.
Part 5: Logs, Streams & Geography
- distributed/chapters/17-logs-exactly-once.html · ch 17 · deep · Logs, Streams & Exactly-Once: Partitioned logs, in-sync replicas, consumer groups, and what exactly-once processing can really mean.
- distributed/chapters/18-multi-region.html · ch 18 · core · Multi-Region Systems: Speed-of-light budgets, leader placement, active-active writes, conflict handling and failing over a region.
Part 6: Verification
- distributed/chapters/19-testing.html · ch 19 · deep · Testing Distributed Systems: Fault injection, Jepsen-style history checking and deterministic simulation that replays any bug from a seed.
- distributed/chapters/20-formal-methods.html · ch 20 · core · Specifying with TLA+: Writing a design as states and actions, checking invariants with a model checker, and when it is worth it.
- distributed/chapters/21-where-next.html · ch 21 · intro · Where Next: On to Reliability: What you can now reason about, a reading list of the classic papers, and running systems for real.
Labs:
- distributed/labs/lab-01-gossip.html · L1 (after Part 1) · Gossip & Failure Detection: A SWIM-style membership protocol in a simulated network with message loss, slow nodes and real crashes.
- distributed/labs/lab-02-fencing.html · L2 (after Part 1) · Leases & Fencing Tokens: A lease-based lock service, a client that pauses at the worst moment, and storage that refuses stale writers.
- distributed/labs/lab-03-linearizability.html · L3 (after Part 2) · A Linearizability Checker: Record concurrent histories and search for a legal order, then catch a store that serves stale reads.
- distributed/labs/lab-04-paxos.html · L4 (after Part 3) · Multi-Paxos Replicated Log: Paxos acceptors and proposers over a lossy, reordering network, then a replicated key-value store on top.
- distributed/labs/lab-05-two-phase-commit.html · L5 (after Part 4) · Two-Phase Commit & Recovery: A coordinator and participants with write-ahead logs, crash recovery, presumed abort and the blocking window.
- distributed/labs/lab-06-crdts.html · L6 (after Part 4) · CRDTs That Converge: Counters, an observed-remove set and a register, proven to converge by randomized merge-order tests.
- distributed/labs/lab-07-simulation.html · L7 (after Part 6) · Deterministic Simulation Testing: A seeded simulator that finds, replays and shrinks a hidden bug in a replicated store.
Cases:
- distributed/cases/case-01-chubby.html · C1 · Chubby: Google's Lock Service [Coarse-grained locks & sequencers]: A Paxos-backed lock service that became Google's naming system, and why it chose coarse locks.
- distributed/cases/case-02-zookeeper.html · C2 · ZooKeeper: Wait-Free Coordination [Coordination kernel]: Simple primitives, watches and ordering guarantees that let clients build their own locks and elections.
- distributed/cases/case-03-redlock.html · C3 · The Redlock Debate [Locks without fencing]: Two experts argue about a Redis locking algorithm, and what it teaches about timing assumptions.
- distributed/cases/case-04-jepsen-etcd.html · C4 · Jepsen Tests etcd [Testing the guarantees]: What an independent test of a Raft-based store found about reads, watches and locks.
- distributed/cases/case-05-percolator.html · C5 · Percolator: Transactions on Bigtable [Snapshot isolation on a KV store]: Incremental indexing at Google with client-driven two-phase commit and a timestamp oracle.
- distributed/cases/case-06-cloudflare-partial-partition.html · C6 · A Byzantine Failure in the Real World [Partial partitions]: A switch that dropped some traffic but not all, a confused Raft cluster and a long outage.
- distributed/cases/case-07-kafka-exactly-once.html · C7 · Kafka's Exactly-Once Semantics [Idempotence & transactions]: Idempotent producers, transactional writes and read-committed consumers, and what the guarantee covers.
- distributed/cases/case-08-figma-multiplayer.html · C8 · Figma's Multiplayer Engine [CRDT-inspired merging]: Real-time collaboration with a central server and per-property last-writer-wins, not a pure CRDT.
- distributed/cases/case-09-foundationdb.html · C9 · FoundationDB: Simulation First [Deterministic simulation]: A database built so that its whole cluster can run, fail and be replayed inside one deterministic process.
- distributed/cases/case-10-aws-tla.html · C10 · Formal Methods at AWS [Specifications that find bugs]: Engineers using TLA+ on S3, DynamoDB and more, and the subtle bugs it found before production did.
Studios:
- distributed/studios/studio-01-lock-service.html · S1 (after Part 3) · Design a Lock & Leader-Election Service: Leases, fencing, sessions and watches for thousands of clients, built on a consensus group.
- distributed/studios/studio-02-collab-editor.html · S2 (after Part 4) · Design a Collaborative Editor: Real-time multi-user editing with offline support, merging and a server that may not be needed.
- distributed/studios/studio-03-multi-region-kv.html · S3 (after Part 5) · Design a Multi-Region Key-Value Store: Per-key consistency choices, replica placement, failover and the latency every choice costs.
Toolbox (distributed/toolbox.html#id):
- #maelstrom · Maelstrom & Gossip Glomers · chapters 03,08,10,15: Write nodes in any language and have a workbench simulate networks, faults and check correctness.
- #jepsen · Jepsen · chapters 05,19: A framework that runs real databases, injects partitions and checks the recorded histories.
- #porcupine · Porcupine & Knossos · chapters 05,19: Linearizability checkers that take a history of operations and look for a legal order.
- #tlaplus · TLA+ & the TLC model checker · chapters 20,09,13: Write a design as a state machine and let the model checker explore every interleaving.
- #etcd · etcd & etcdctl · chapters 10,11,04: Run a real three-node Raft cluster, watch leader changes and take leases.
- #zookeeper · ZooKeeper CLI · chapters 11: Create ephemeral and sequential znodes and build an election recipe by hand.
- #toxiproxy · Toxiproxy & tc netem · chapters 03,18,19: Add latency, loss and partitions between real processes to see protocols misbehave.
- #kafka · Kafka CLI tools · chapters 17: Create partitioned topics, run consumer groups and inspect offsets and replicas.

## Course 5 · Reliability & Operations  (id "ops", folder reliability/)

Part 0: Orientation
- reliability/chapters/00-start-here.html · ch 00 · intro · Start Here: From building systems to running them: what operations is, and how this course builds on the first four.
Part 1: Defining Reliability
- reliability/chapters/01-availability-math.html · ch 01 · deep · What Reliability Means: Nines, serial and parallel composition, MTBF and MTTR, and why recovery speed often beats prevention.
- reliability/chapters/02-slos-error-budgets.html · ch 02 · deep · SLIs, SLOs & Error Budgets: Measuring what users feel, choosing targets, and spending an error budget on purpose.
- reliability/chapters/03-sre-toil.html · ch 03 · intro · Toil, Automation & Ownership: The SRE model, toil budgets, and who carries the pager for what.
Part 2: Observability
- reliability/chapters/04-metrics.html · ch 04 · deep · Metrics, Percentiles & Histograms: Counters, gauges and histograms, why percentiles cannot be averaged, RED and USE, and the cardinality trap.
- reliability/chapters/05-logs-events.html · ch 05 · core · Logs & Structured Events: From printf to wide structured events, log levels, sampling and the cost of keeping everything.
- reliability/chapters/06-tracing.html · ch 06 · deep · Distributed Tracing: Spans, context propagation, sampling, critical paths and OpenTelemetry.
- reliability/chapters/07-alerting-oncall.html · ch 07 · core · Alerting & On-Call: Symptom-based alerts, multi-window burn-rate alerting, runbooks and fighting alert fatigue.
Part 3: Performance & Capacity
- reliability/chapters/08-queueing-theory.html · ch 08 · deep · Queueing Theory for Engineers: Utilization, the latency knee, M/M/1 and M/M/c intuition, variability and why 80% busy is already busy.
- reliability/chapters/09-tail-latency.html · ch 09 · deep · Tail Latency at Scale: Fan-out amplification, hedged and tied requests, and designing for the 99.9th percentile.
- reliability/chapters/10-load-testing-capacity.html · ch 10 · core · Load Testing & Capacity Planning: Open versus closed load, coordinated omission, headroom, forecasting and saturation tests.
- reliability/chapters/11-overload.html · ch 11 · deep · Overload, Load Shedding & Metastability: Admission control, adaptive concurrency limits, retry budgets and failures that sustain themselves.
Part 4: Changing Production Safely
- reliability/chapters/12-deployments.html · ch 12 · deep · Deployment Strategies: Rolling, blue-green and canary releases, automated canary analysis and fast, boring rollbacks.
- reliability/chapters/13-config-iac.html · ch 13 · core · Configuration & Infrastructure as Code: Config changes as the leading cause of outages, staged config rollout, GitOps and immutable infrastructure.
- reliability/chapters/14-orchestration.html · ch 14 · core · Containers & Orchestration: Kubernetes from first principles: desired state, controllers, pods, services, probes, requests and limits.
- reliability/chapters/15-blast-radius.html · ch 15 · deep · Blast Radius: Cells, Shuffle Sharding & Static Stability: Containing failures by design: cells, shuffle sharding, control versus data planes and static stability.
Part 5: When Things Break
- reliability/chapters/16-incident-response.html · ch 16 · core · Incident Response: Detection, roles, mitigation before diagnosis, communication and knowing when it is over.
- reliability/chapters/17-postmortems.html · ch 17 · core · Postmortems & Learning from Incidents: Blameless reviews, contributing factors instead of root causes, and turning incidents into change.
- reliability/chapters/18-disaster-recovery.html · ch 18 · core · Backups & Disaster Recovery: RPO and RTO, restore testing, region evacuation and the backups that only count if you can restore them.
- reliability/chapters/19-chaos-gamedays.html · ch 19 · core · Chaos Engineering & Game Days: Hypotheses, steady state, controlled experiments and rehearsing failure before it rehearses you.
Part 6: Sustaining Systems
- reliability/chapters/20-cost-efficiency.html · ch 20 · intro · Cost & Efficiency: Cloud cost models, utilization, right-sizing and treating efficiency as an engineering property.
- reliability/chapters/21-where-next.html · ch 21 · intro · Where Next: On to Security: What you can now run and reason about, and why the next course assumes some users are adversaries.
Labs:
- reliability/labs/lab-01-slo-burn.html · L1 (after Part 1) · SLOs & Burn-Rate Alerts: Compute SLIs and error budgets from request logs, then build multi-window burn-rate alerts and test them on synthetic incidents.
- reliability/labs/lab-02-metrics.html · L2 (after Part 2) · A Metrics Library: Counters and histograms with buckets, mergeable percentiles across hosts, and an exposition endpoint.
- reliability/labs/lab-03-tracing.html · L3 (after Part 2) · Tracing from Scratch: Propagate trace context across simulated services, rebuild trace trees and find the critical path.
- reliability/labs/lab-04-queueing.html · L4 (after Part 3) · Queues, Load Tests & Coordinated Omission: A discrete-event simulator checked against queueing formulas, and a load generator that does not lie.
- reliability/labs/lab-05-load-shedding.html · L5 (after Part 3) · Adaptive Concurrency & Load Shedding: Drive a simulated service into a metastable failure, then protect it with admission control and AIMD limits.
- reliability/labs/lab-06-canary.html · L6 (after Part 4) · Automated Canary Analysis: Compare canary and baseline metrics statistically and decide promote or roll back, without fooling yourself.
Cases:
- reliability/cases/case-01-tail-at-scale.html · C1 · The Tail at Scale [Tail-tolerant design]: Google's lessons on why rare slowness dominates large fan-out systems, and the techniques that tame it.
- reliability/cases/case-02-aws-2021.html · C2 · AWS us-east-1, December 2021 [Hidden internal dependencies]: Congestion on an internal network, monitoring that went dark, and slow recovery for many services.
- reliability/cases/case-03-slack-2021.html · C3 · Slack's January 2021 Outage [Scaling under a surge]: The first working day of the year, a saturated network layer and autoscaling that made things worse.
- reliability/cases/case-04-roblox-2021.html · C4 · Roblox: 73 Hours Down [Shared infrastructure failure]: A coordination system under unusual load, a storage pathology and a long, careful recovery.
- reliability/cases/case-05-crowdstrike-2024.html · C5 · CrowdStrike, July 2024 [Unstaged content rollout]: A content update pushed to millions of machines at once, and why staged rollout matters for config too.
- reliability/cases/case-06-atlassian-2022.html · C6 · Atlassian: The Two-Week Restore [Recovery at the wrong granularity]: Sites deleted by a maintenance script, and backups that could not restore a few customers quickly.
- reliability/cases/case-07-kayenta.html · C7 · Netflix Kayenta: Canaries by Statistics [Automated canary analysis]: Comparing canary and baseline clusters metric by metric before a release goes everywhere.
- reliability/cases/case-08-static-stability.html · C8 · Static Stability at AWS [Data plane survives control plane]: Designing systems that keep working when the systems that change them are down.
Studios:
- reliability/studios/studio-01-observability.html · S1 (after Part 2) · Design Observability for Checkout: SLIs, SLOs, dashboards, traces and alerts for a checkout flow that spans six services.
- reliability/studios/studio-02-flash-sale.html · S2 (after Part 3) · Prepare for a Flash Sale: Forecast, load-test, add headroom and plan degradation for a launch with twenty times normal traffic.
- reliability/studios/studio-03-incident.html · S3 (after Part 5) · Run an Incident: A Tabletop Exercise: A staged outage you work through as incident commander, from first page to postmortem.
Toolbox (reliability/toolbox.html#id):
- #prometheus · Prometheus & PromQL · chapters 04,07,02: Scrape metrics, query rates and histograms, and write the alert rules you designed.
- #grafana · Grafana · chapters 04,02: Turn metrics into dashboards that answer one question each.
- #otel · OpenTelemetry & Jaeger · chapters 06,05: Instrument a small service, propagate context and look at real traces.
- #loadgen · k6, wrk2 & vegeta · chapters 10,08,09: Generate open-model load at a fixed rate and read latency histograms honestly.
- #kubectl · kind & kubectl · chapters 14,12: Run Kubernetes on your laptop, roll out a deployment, break a probe and watch reconciliation.
- #stress · stress-ng & tc netem · chapters 11,19: Starve a machine of CPU, memory or network and observe how your service degrades.
- #chaos · Chaos tools · chapters 19: Chaos Mesh, Toxiproxy and friends: controlled fault injection with a blast radius you choose.
- #runbook · Runbooks & incident templates · chapters 16,17,07: Plain-text templates for runbooks, incident channels and postmortems you can copy.

## Course 6 · Security Engineering  (id "sec", folder security/)

Part 0: Orientation
- security/chapters/00-start-here.html · ch 00 · intro · Start Here: Attackers, assets and trust: how security fits into everything the earlier courses built.
Part 1: Foundations
- security/chapters/01-threat-modeling.html · ch 01 · deep · Threat Modeling: Assets, adversaries, trust boundaries, STRIDE and attack trees: finding the weak points before an attacker does.
- security/chapters/02-principles.html · ch 02 · core · Security Design Principles: Least privilege, defence in depth, fail-safe defaults, complete mediation and a small trusted computing base.
- security/chapters/03-applied-crypto.html · ch 03 · deep · Applied Cryptography: Hashes, MACs, authenticated encryption, public keys, signatures and randomness, and the mistakes that break them.
- security/chapters/04-keys-secrets-pki.html · ch 04 · deep · Keys, Secrets & PKI: Key management, envelope encryption, rotation, secret stores, certificate authorities and mutual TLS.
Part 2: Identity & Access
- security/chapters/05-authentication.html · ch 05 · deep · Authentication: Password storage, multi-factor authentication, passkeys and credential stuffing.
- security/chapters/06-sessions-tokens.html · ch 06 · core · Sessions, Cookies & Tokens: Server sessions versus signed tokens, JWT pitfalls, cookie flags, refresh tokens and revocation.
- security/chapters/07-oauth-oidc.html · ch 07 · deep · OAuth 2.0 & OpenID Connect: Delegated access, the authorization-code flow with PKCE, scopes, ID tokens and single sign-on.
- security/chapters/08-authorization.html · ch 08 · deep · Authorization: RBAC, ABAC and relationship-based access, policy engines, the confused deputy and broken object-level authorization.
Part 3: Application Security
- security/chapters/09-injection.html · ch 09 · deep · Injection & Untrusted Input: SQL and command injection, path traversal and unsafe deserialization, and why parameterization beats filtering.
- security/chapters/10-web-security.html · ch 10 · deep · The Browser Security Model: Same-origin policy, XSS, CSRF, CORS, content security policy and cookie attributes.
- security/chapters/11-ssrf-server-side.html · ch 11 · core · SSRF & Server-Side Risks: Making your server fetch what the attacker wants, cloud metadata endpoints and other server-side traps.
- security/chapters/12-memory-supply-chain.html · ch 12 · core · Memory Safety & the Supply Chain: Buffer overflows in one picture, memory-safe languages, dependencies, signed builds and SBOMs.
Part 4: Infrastructure Security
- security/chapters/13-zero-trust.html · ch 13 · core · Network Security & Zero Trust: Segmentation, firewalls and why the trusted internal network is a myth: identity-aware access everywhere.
- security/chapters/14-cloud-container.html · ch 14 · core · Cloud & Container Security: Cloud IAM, least-privilege roles, metadata services, container isolation and secrets in orchestrators.
- security/chapters/15-multi-tenancy.html · ch 15 · deep · Multi-Tenancy & Isolation: Silo, pool and bridge models, tenant-aware data access, noisy neighbours and per-tenant keys.
- security/chapters/16-abuse-dos.html · ch 16 · core · Abuse, Bots & Denial of Service: Credential stuffing, scraping, fraud signals, DDoS mitigation and designing for adversarial load.
Part 5: Data & Operations
- security/chapters/17-data-protection.html · ch 17 · deep · Data Protection & Privacy: Encryption at rest and in transit, tokenization, minimization, deletion across logs and backups, and residency.
- security/chapters/18-detection-response.html · ch 18 · core · Detection & Security Incidents: Audit logs, detection engineering, security incident response and what to keep for forensics.
- security/chapters/19-secure-design-review.html · ch 19 · core · Secure Design Reviews: Security sections in design docs, a review checklist, secure defaults and a security-minded engineering culture.
- security/chapters/20-where-next.html · ch 20 · intro · Where Next: On to System Design: What you can now defend, a reading list, and carrying a security lens into every design.
Labs:
- security/labs/lab-01-passwords-macs.html · L1 (after Part 1) · Passwords, MACs & Timing: Store passwords with a slow salted hash, upgrade hashes on login, sign messages with HMAC and stop replays.
- security/labs/lab-02-tokens.html · L2 (after Part 2) · Build and Break a Token Format: A JWT-like signed token, then the attacks: algorithm confusion, missing checks, expiry and revocation.
- security/labs/lab-03-oauth-pkce.html · L3 (after Part 2) · OAuth with PKCE, Simulated: An in-process authorization server, client and API, with redirect, state and PKCE checks you can attack.
- security/labs/lab-04-authz-engine.html · L4 (after Part 2) · A Relationship-Based Authorization Engine: From roles to Zanzibar-style relation tuples, with tests that catch insecure direct object references.
- security/labs/lab-05-injection.html · L5 (after Part 3) · Find and Fix Injection: Exploit a vulnerable app's SQL, path and URL-fetch handling, then fix each bug for good.
- security/labs/lab-06-envelope-encryption.html · L6 (after Part 5) · Envelope Encryption & Crypto-Shredding: Per-tenant data keys wrapped by a master key, key rotation, and deleting a tenant by destroying its key.
Cases:
- security/cases/case-01-heartbleed.html · C1 · Heartbleed [Memory safety]: A missing bounds check in OpenSSL that leaked server memory, including private keys, to anyone who asked.
- security/cases/case-02-equifax.html · C2 · Equifax, 2017 [Patch and inventory]: An unpatched web framework, an expired certificate on a monitoring device and months of undetected access.
- security/cases/case-03-capital-one.html · C3 · Capital One, 2019 [SSRF to cloud credentials]: A misconfigured firewall, a metadata endpoint and an over-privileged role.
- security/cases/case-04-log4shell.html · C4 · Log4Shell [Injection through a feature]: A logging library that looked up and loaded code named inside log messages.
- security/cases/case-05-storm-0558.html · C5 · Storm-0558 and a Stolen Signing Key [Key management]: A consumer signing key that could mint enterprise tokens, and what an independent review concluded.
- security/cases/case-06-xz-backdoor.html · C6 · The xz Backdoor [Open-source supply chain]: Years of patient social engineering, a hidden build-time payload and a half-second delay that gave it away.
- security/cases/case-07-beyondcorp.html · C7 · BeyondCorp: Google's Zero Trust [No trusted network]: Moving access decisions from the network perimeter to devices and users.
- security/cases/case-08-zanzibar.html · C8 · Zanzibar: Authorization at Google Scale [Relationship-based access]: One global system answering permission checks for many products, with consistency tokens against stale ACLs.
Studios:
- security/studios/studio-01-saas-identity.html · S1 (after Part 4) · Design Identity & Access for a Multi-Tenant SaaS: Single sign-on, roles and sharing, tenant isolation, admin impersonation and audit.
- security/studios/studio-02-threat-model.html · S2 (after Part 3) · Threat-Model a File-Sharing Service: Uploads, previews, share links and an API: find the threats, rank them and design the mitigations.
- security/studios/studio-03-secrets-manager.html · S3 (after Part 5) · Design a Secrets Manager: Storing, leasing and rotating secrets for thousands of services, and surviving the loss of the master key holder.
Toolbox (security/toolbox.html#id):
- #zap · OWASP ZAP · chapters 09,10,11: An intercepting proxy and scanner for testing your own web apps.
- #semgrep · Semgrep & static analysis · chapters 09,19: Search code for insecure patterns with rules you can read and write.
- #deps · Dependency & image scanners · chapters 12,14: pip-audit, OSV-Scanner and Trivy: find known-vulnerable packages before attackers do.
- #secrets-scan · Secret scanners · chapters 04,12: gitleaks and friends: catch keys committed to a repository.
- #nmap · nmap · chapters 13,14: See which ports and services your own machines actually expose.
- #jwt-tools · Token and certificate inspection · chapters 06,07,04: Decode JWTs, inspect certificates and test TLS settings from the command line.

## Course 7 · System Design Studio  (id "design", folder design/)

Part 0: Orientation
- design/chapters/00-start-here.html · ch 00 · intro · Start Here: How design problems differ from coding problems, and how to use the worked designs and studios.
Part 1: The Method
- design/chapters/01-framework.html · ch 01 · deep · A Framework for Design Problems: Requirements, estimates, interfaces, data, architecture, deep dives and trade-offs, in that order and why.
- design/chapters/02-estimation.html · ch 02 · deep · Back-of-the-Envelope Estimation: Numbers to remember, QPS, storage, bandwidth and machine counts, and sanity checks that catch mistakes.
- design/chapters/03-building-blocks.html · ch 03 · core · The Building Blocks, Revisited: Load balancers, caches, CDNs, queues, databases, object stores and search: what each buys and costs.
- design/chapters/04-tradeoffs-communication.html · ch 04 · core · Trade-offs, Communication & Design Docs: Thinking aloud, driving the discussion, writing a design doc, and what senior signals look like.
Part 2: Foundational Designs
- design/chapters/05-rate-limiter.html · ch 05 · deep · Design a Rate Limiter: Token buckets and sliding windows, local versus global limits, and failing open or closed.
- design/chapters/06-distributed-cache.html · ch 06 · deep · Design a Distributed Cache: Partitioning, replication, eviction, hot keys and the consistency of cached data.
- design/chapters/07-unique-ids.html · ch 07 · core · Design Unique ID Generation: UUIDs, ticket servers, Snowflake-style IDs, ordering and clock problems.
- design/chapters/08-object-storage.html · ch 08 · deep · Design Object Storage: Metadata versus data, erasure coding, durability arithmetic and multipart uploads.
Part 3: Social & Real-Time
- design/chapters/09-news-feed.html · ch 09 · deep · Design a News Feed: Fan-out on write versus read, celebrities, ranking and caching timelines.
- design/chapters/10-chat-presence.html · ch 10 · deep · Design Chat & Presence: Persistent connections, message ordering, delivery receipts, group fan-out and who is online.
- design/chapters/11-search-typeahead.html · ch 11 · core · Design Search & Typeahead: Inverted indexes at scale, tries and prefix caches, ranking and freshness.
- design/chapters/12-top-k-trending.html · ch 12 · core · Design Top-K & Trending: Heavy hitters over streams, count-min sketches, windows and approximate answers.
Part 4: Media, Geo & Marketplaces
- design/chapters/13-video-streaming.html · ch 13 · deep · Design Video Streaming: Upload, transcoding pipelines, adaptive bitrate, CDNs and the economics of bytes.
- design/chapters/14-ride-matching.html · ch 14 · deep · Design Ride Matching: Location updates, geospatial indexes, matching and the dispatch state machine.
- design/chapters/15-ticketing.html · ch 15 · core · Design Ticketing & Flash Sales: Seat holds with expiry, contention on hot inventory, queues and fairness.
Part 5: Money & Infrastructure
- design/chapters/16-payments.html · ch 16 · deep · Design a Payment System: Idempotency, double-entry ledgers, payment service providers, reconciliation and exactly-once money.
- design/chapters/17-job-scheduler.html · ch 17 · core · Design a Distributed Job Scheduler: Delayed and recurring jobs, leases, retries, priorities and at-least-once execution.
- design/chapters/18-web-crawler.html · ch 18 · core · Design a Web Crawler: The frontier, politeness, deduplication, traps and crawling a billion pages.
- design/chapters/19-telemetry-platform.html · ch 19 · core · Design a Metrics & Logging Platform: High-volume ingestion, time-series storage, downsampling, cardinality and queries.
Part 6: Beyond
- design/chapters/20-ml-systems.html · ch 20 · core · Designing with ML & LLMs: Model serving, feature stores, embeddings and vector search, retrieval-augmented generation and their failure modes.
- design/chapters/21-where-next.html · ch 21 · intro · Where Next: Growing as a Senior Engineer: Judgment, influence and continued learning, and how to keep this whole path fresh.
Labs:
- design/labs/lab-01-estimation.html · L1 (after Part 1) · Estimation Drills: A napkin-maths toolkit and a checked set of estimation problems, from QPS to disk counts.
- design/labs/lab-02-rate-limiters.html · L2 (after Part 2) · Rate Limiters: Token bucket, sliding-window log and counter, then a global limiter over a shared store with clock skew.
- design/labs/lab-03-feed-fanout.html · L3 (after Part 3) · Feed Fan-out Simulator: Compare push, pull and hybrid timelines on a power-law follower graph, measuring work and latency.
- design/labs/lab-04-sketches.html · L4 (after Part 3) · Sketches: Count-Min, HyperLogLog & Top-K: Approximate counting with error bounds you can test, and a streaming top-K.
- design/labs/lab-05-geo-index.html · L5 (after Part 4) · A Geospatial Index: Geohashes and a quadtree for nearest-driver queries, benchmarked against brute force.
- design/labs/lab-06-job-scheduler.html · L6 (after Part 5) · A Durable Job Scheduler: Delayed jobs, leases, retries with backoff and idempotent handlers, tested with crashes.
Cases:
- design/cases/case-01-twitter-timelines.html · C1 · Twitter's Timelines at Scale [Fan-out on write]: Precomputed home timelines in memory, and the special handling that very large accounts need.
- design/cases/case-02-instagram-ids.html · C2 · Sharding & IDs at Instagram [Time-ordered IDs in the database]: Generating sortable 64-bit IDs inside PostgreSQL shards without a central service.
- design/cases/case-03-whatsapp.html · C3 · WhatsApp: Millions of Connections per Server [Lightweight processes]: Erlang, FreeBSD tuning and a tiny team serving a huge messaging network.
- design/cases/case-04-uber-h3.html · C4 · Uber's H3 Hexagonal Grid [Geospatial indexing]: Why hexagons, how hierarchical cells work, and what a grid buys a marketplace.
- design/cases/case-05-netflix-open-connect.html · C5 · Netflix Open Connect [Own the edge]: Netflix's own CDN appliances inside ISPs, filled off-peak and steered per request.
- design/cases/case-06-stripe-idempotency.html · C6 · Idempotency Keys at Stripe [Safe retries for money]: Making payment APIs safe to retry, and the state machine behind each key.
- design/cases/case-07-slack-realtime.html · C7 · Slack's Real-Time Messaging [Channel servers & gateways]: Consistent-hashed channel servers, gateway servers near users and fan-out of every message.
- design/cases/case-08-dropbox-magic-pocket.html · C8 · Dropbox Magic Pocket [Exabyte object storage]: Leaving the public cloud for an in-house block store with erasure coding and verification everywhere.
Studios:
- design/studios/studio-01-file-sync.html · S1 (after Part 2) · Design File Sync (Dropbox): Chunking, deduplication, metadata, sync conflicts and clients that go offline for weeks.
- design/studios/studio-02-photo-sharing.html · S2 (after Part 3) · Design Photo Sharing (Instagram): Uploads, a feed, likes and comments, a CDN and the hot accounts that break naive designs.
- design/studios/studio-03-code-judge.html · S3 (after Part 5) · Design an Online Code Judge: Untrusted code in sandboxes, a submission queue, contest spikes and fair results.
- design/studios/studio-04-booking.html · S4 (after Part 4) · Design a Hotel Booking System: Inventory by night, no double bookings, holds, overbooking policy and search that scales.
- design/studios/studio-05-exchange.html · S5 (after Part 5) · Design a Stock Exchange: A matching engine, a sequenced input log, market data fan-out and microseconds that matter.
- design/studios/studio-06-message-queue.html · S6 (after Part 5) · Design a Distributed Message Queue: Partitions, replication, consumer groups, retention and delivery guarantees, built from scratch.
- design/studios/studio-07-ad-clicks.html · S7 (after Part 5) · Design an Ad Click Aggregator: Billions of events, windowed counts, exactly-once billing and reconciliation.
- design/studios/studio-08-live-streaming.html · S8 (after Part 6) · Design Live Streaming with Chat: Ingest, low-latency delivery, a chat room of a million viewers and a broadcast that cannot buffer.
Toolbox (design/toolbox.html#id):
- #excalidraw · Excalidraw & whiteboards · chapters 01,04: Sketch boxes and arrows fast, the way you will in a design review or interview.
- #napkin · Napkin-maths reference · chapters 02,08: Latency and throughput numbers worth memorising, and how to derive the rest.
- #design-doc · Design-doc templates · chapters 04,01: A one-page and a full design-doc template, with a review checklist.
- #mock · Mock interview kit · chapters 01,04,21: Timers, prompts and a scoring rubric for practising with a friend.
- #redis-lab · Redis for prototyping · chapters 05,06,12: Try rate limiters, caches and sorted-set leaderboards on a real data structure server.

## A0 · Math & Code for Machine Learning  (id "mlf", folder ml-foundations/)

Part 0: Orientation
- ml-foundations/chapters/00-start-here.html · ch 00 · intro · Start Here: What AI systems engineers build, the nine courses, and how to use them without drowning.
Part 1: Python for ML Work
- ml-foundations/chapters/01-python-numerics.html · ch 01 · core · Python for Numerical Work: Numbers, lists and loops, why pure Python is slow for maths, and the idea of vectorising.
- ml-foundations/chapters/02-numpy-arrays.html · ch 02 · deep · NumPy, Arrays & Broadcasting: Shapes, strides, axes and broadcasting: the mental model behind every tensor library.
- ml-foundations/chapters/03-data-wrangling.html · ch 03 · core · Data Wrangling: pandas, SQL & Tidy Data: Loading, joining, grouping and cleaning tables, and the questions to ask any dataset.
- ml-foundations/chapters/04-reproducible-experiments.html · ch 04 · core · Reproducible Experiments: Environments, pinned versions, seeds, notebooks versus scripts and experiment logs.
Part 2: Linear Algebra
- ml-foundations/chapters/05-vectors-similarity.html · ch 05 · deep · Vectors, Dot Products & Similarity: Vectors as arrows and as lists, length, angle, cosine similarity and projections.
- ml-foundations/chapters/06-matrices.html · ch 06 · deep · Matrices as Functions: Matrix multiplication as composing transformations, shapes as contracts, and inverses.
- ml-foundations/chapters/07-decompositions.html · ch 07 · deep · Eigenvectors, SVD & Low Rank: Eigenvectors, the singular value decomposition and why low-rank structure is everywhere.
Part 3: Calculus & Optimisation
- ml-foundations/chapters/08-derivatives.html · ch 08 · deep · Derivatives & the Chain Rule: Slopes, partial derivatives, gradients and the one rule that makes deep learning possible.
- ml-foundations/chapters/09-autodiff.html · ch 09 · deep · Automatic Differentiation: Computation graphs, forward and reverse mode, and a tiny autograd engine built by hand.
- ml-foundations/chapters/10-optimisers.html · ch 10 · deep · Gradient Descent & Optimisers: Learning rates, SGD, momentum, Adam and AdamW, schedules and what can go wrong.
- ml-foundations/chapters/11-numerics.html · ch 11 · core · Floating Point & Numerical Stability: How floats work, overflow and underflow, stable softmax, and fp16, bf16 and fp8.
Part 4: Probability & Information
- ml-foundations/chapters/12-probability.html · ch 12 · deep · Probability, Distributions & Sampling: Random variables, common distributions, expectation, Bayes' rule and sampling.
- ml-foundations/chapters/13-likelihood-losses.html · ch 13 · deep · Maximum Likelihood & Loss Functions: Why squared error and cross-entropy are not arbitrary: they are likelihoods in disguise.
- ml-foundations/chapters/14-information-theory.html · ch 14 · deep · Entropy, Cross-Entropy & KL Divergence: Surprise, bits, perplexity and the divergence that appears in every post-training method.
- ml-foundations/chapters/15-statistics.html · ch 15 · deep · Statistics for Experiments: Confidence intervals, the bootstrap, hypothesis tests, power and the peeking trap.
Part 5: Working Practice
- ml-foundations/chapters/16-reading-papers.html · ch 16 · core · Reading Papers Efficiently: A three-pass method, what to skip, how to check claims and how to reproduce a result.
- ml-foundations/chapters/17-compute-costs.html · ch 17 · core · GPUs, Clouds & What Compute Costs: What a GPU is good at, memory versus FLOPs, renting hardware and estimating a bill.
- ml-foundations/chapters/18-technical-writing.html · ch 18 · core · Writing for Engineers: Design docs, experiment reports and error-analysis memos that people actually read.
- ml-foundations/chapters/19-ai-assistants.html · ch 19 · intro · Learning with AI Assistants: Using coding assistants to go faster without outsourcing the understanding.
Labs:
- ml-foundations/labs/lab-01-linalg.html · L1 (after Part 2) · A Small Linear Algebra Library: Vectors, matrix multiply, transpose, Gram-Schmidt and power iteration, tested against hand values.
- ml-foundations/labs/lab-02-autograd.html · L2 (after Part 3) · Build an Autograd Engine: A scalar Value class with reverse-mode autodiff, checked against numerical gradients.
- ml-foundations/labs/lab-03-optimisers.html · L3 (after Part 3) · The Optimiser Race: SGD, momentum, RMSProp, Adam and AdamW on classic test surfaces, with schedules and clipping.
- ml-foundations/labs/lab-04-likelihood.html · L4 (after Part 4) · Sampling, Likelihood & Entropy: Samplers, maximum-likelihood fits, stable log-softmax, temperature, entropy and KL.
- ml-foundations/labs/lab-05-statistics.html · L5 (after Part 4) · A Statistics Toolkit for Experiments: Bootstrap intervals, permutation tests, power by simulation and a demonstration of peeking.
Cases:
- ml-foundations/cases/case-01-reinhart-rogoff.html · C1 · A Spreadsheet Error That Shaped Policy [Reproducible analysis]: An influential economics result that a student could not reproduce, and what the spreadsheet hid.
- ml-foundations/cases/case-02-patriot-missile.html · C2 · The Patriot Missile Clock [Floating-point drift]: A tiny rounding error, accumulated over 100 hours of uptime, and a missed interception.
- ml-foundations/cases/case-03-adamw.html · C3 · AdamW: Weight Decay Done Right [Optimiser details matter]: Why L2 regularisation and weight decay stop being the same thing inside Adam.
- ml-foundations/cases/case-04-mixed-precision.html · C4 · Mixed-Precision Training [Fewer bits, same model]: Half-precision arithmetic, loss scaling and master weights: how training got twice as cheap.
- ml-foundations/cases/case-05-peeking.html · C5 · Peeking at A/B Tests [Valid stopping rules]: Why checking a running experiment every day inflates false positives, and how sequential tests fix it.
Studios:
- ml-foundations/studios/studio-01-experiment-design.html · S1 (after Part 4) · Design an Experiment That Can Fail: Decide whether a change really helped: metric, sample size, stopping rule and what would change your mind.
- ml-foundations/studios/studio-02-compute-budget.html · S2 (after Part 5) · Budget the Compute for a Project: Turn a research plan into GPU-hours, memory, storage and a bill, with the risky assumptions named.
Toolbox (ml-foundations/toolbox.html#id):
- #jupyter · Jupyter & notebooks · chapters 01,03,04: Interactive exploration, and the discipline that keeps notebooks reproducible.
- #numpy · NumPy · chapters 02,05,06,07: The array library underneath almost every numerical Python tool.
- #pandas · pandas & DuckDB · chapters 03: Tables in memory, and SQL over files without a server.
- #uv · uv & virtual environments · chapters 04: Fast, pinned, reproducible Python environments.
- #plotting · matplotlib · chapters 03,12,15: Plots that answer a question, and the habit of looking at your data.
- #free-gpus · Colab & Kaggle notebooks · chapters 17: Free and cheap GPUs for learning, and their limits.
- #papers · arXiv, Semantic Scholar & Papers with Code · chapters 16: Finding, tracking and checking papers and their code.

## A1 · Machine Learning & Data Science  (id "ml", folder ml/)

Part 0: Orientation
- ml/chapters/00-start-here.html · ch 00 · intro · Start Here: Learning from examples, the data-science loop, and where this course fits.
Part 1: Framing Problems
- ml/chapters/01-generalisation.html · ch 01 · deep · What Learning Is: Generalisation: Training, validation and test sets, overfitting, underfitting and the no-free-lunch idea.
- ml/chapters/02-framing-metrics.html · ch 02 · deep · Framing Problems & Choosing Metrics: Turning a business question into a prediction task with a metric that matches the cost of errors.
- ml/chapters/03-eda.html · ch 03 · core · Exploratory Data Analysis: Distributions, missingness, duplicates, shifts between train and test, and the questions to ask first.
- ml/chapters/04-baselines.html · ch 04 · core · Baselines First: Majority class, simple rules and linear models: the numbers every fancy model must beat.
Part 2: Core Models
- ml/chapters/05-linear-models.html · ch 05 · deep · Linear & Logistic Regression: Fitting lines and probabilities, gradient descent, and reading coefficients carefully.
- ml/chapters/06-regularisation.html · ch 06 · deep · Regularisation & the Bias-Variance Trade-off: Why simpler models generalise, L1 and L2 penalties, and learning curves.
- ml/chapters/07-neighbours-bayes.html · ch 07 · core · Nearest Neighbours, Naive Bayes & Kernels: Similarity-based and probabilistic classifiers, and the kernel trick in one picture.
- ml/chapters/08-decision-trees.html · ch 08 · deep · Decision Trees: Splits, impurity, depth, and why a single tree is both readable and unstable.
- ml/chapters/09-ensembles-boosting.html · ch 09 · deep · Random Forests & Gradient Boosting: Bagging, boosting, XGBoost, LightGBM and CatBoost: why boosted trees rule tabular data.
Part 3: Unsupervised Learning
- ml/chapters/10-clustering.html · ch 10 · core · Clustering: k-means, hierarchical clustering and DBSCAN, and how to tell whether clusters are real.
- ml/chapters/11-dimensionality-reduction.html · ch 11 · core · Dimensionality Reduction: PCA, t-SNE and UMAP: compressing and visualising high-dimensional data honestly.
- ml/chapters/12-anomaly-detection.html · ch 12 · core · Anomaly Detection: Statistical, distance-based and isolation methods for finding the rare and the strange.
Part 4: Validation & Trust
- ml/chapters/13-cross-validation.html · ch 13 · deep · Cross-Validation Done Right: k-fold, grouped, stratified and time-based splits that mirror how the model will be used.
- ml/chapters/14-leakage.html · ch 14 · deep · Leakage: The Silent Killer: Target leakage, train-test contamination and preprocessing leaks, and how to hunt them.
- ml/chapters/15-imbalance-calibration.html · ch 15 · deep · Imbalance, Thresholds & Calibration: Rare positives, precision-recall trade-offs, choosing thresholds by cost, and calibrated probabilities.
- ml/chapters/16-interpretability.html · ch 16 · core · Interpreting Models: Permutation importance, partial dependence and SHAP, and what explanations cannot tell you.
Part 5: Features & Competitions
- ml/chapters/17-feature-engineering.html · ch 17 · deep · Feature Engineering: Encodings, aggregates, interactions, target encoding done safely, and features from domain knowledge.
- ml/chapters/18-time-series.html · ch 18 · core · Time Series Forecasting: Trend, seasonality, lag features, backtesting and the forecasting baselines that are hard to beat.
- ml/chapters/19-tabular-deep-learning.html · ch 19 · intro · Tabular Deep Learning & Foundation Models: Neural nets for tables, TabPFN-style foundation models, and when they beat boosted trees.
- ml/chapters/20-competitions.html · ch 20 · core · How Competitions Are Won: Validation strategy, diverse models, stacking and the habits competition winners describe.
Part 6: From Model to Value
- ml/chapters/21-model-to-value.html · ch 21 · core · From Model to Value: Offline metrics versus business outcomes, A/B tests, monitoring, drift and retraining.
Labs:
- ml/labs/lab-01-linear-models.html · L1 (after Part 2) · Linear & Logistic Regression from Scratch: Closed form and gradient descent, L1 and L2 penalties, and log-loss, all checked against hand values.
- ml/labs/lab-02-trees-boosting.html · L2 (after Part 2) · Trees & Gradient Boosting from Scratch: A CART tree, a random forest and a gradient-boosting regressor in plain Python.
- ml/labs/lab-03-unsupervised.html · L3 (after Part 3) · k-means, PCA & Anomalies: k-means++ with restarts, PCA by power iteration, and an isolation-style anomaly score.
- ml/labs/lab-04-leakage-hunt.html · L4 (after Part 4) · The Leakage Hunt: Build a validation harness that catches four planted leaks, including one in preprocessing.
- ml/labs/lab-05-calibration.html · L5 (after Part 4) · Thresholds & Calibration: PR curves, cost-based thresholds, reliability diagrams, Platt scaling and isotonic regression.
- ml/labs/lab-06-features-stacking.html · L6 (after Part 5) · Feature Pipelines & Stacking: Leak-safe target encoding, out-of-fold predictions and a stacked ensemble that beats its parts.
Cases:
- ml/cases/case-01-netflix-prize.html · C1 · The Netflix Prize [Ensembles vs deployability]: A million-dollar ensemble that won the competition and was never fully deployed.
- ml/cases/case-02-google-flu-trends.html · C2 · Google Flu Trends [Drift and spurious features]: Search queries that predicted flu, until they did not, and what the post-mortems found.
- ml/cases/case-03-zillow-offers.html · C3 · Zillow Offers [Model risk in a business]: An algorithmic home-buying business that shut down after its price forecasts met a turning market.
- ml/cases/case-04-amazon-recruiting.html · C4 · A Recruiting Model That Learned Bias [Biased labels]: A CV-screening model trained on past hiring decisions, and why removing words did not fix it.
- ml/cases/case-05-xgboost.html · C5 · XGBoost: A System, Not Just an Algorithm [Engineering wins benchmarks]: Sparsity-aware splits, cache-aware blocks and out-of-core training behind a competition favourite.
- ml/cases/case-06-competition-leaks.html · C6 · Leaks That Won Competitions [Leakage]: Row orders, IDs and timestamps that gave away the answer, and how organisers learned to prevent them.
- ml/cases/case-07-compas.html · C7 · COMPAS and Competing Definitions of Fair [Calibration vs error balance]: A risk score that was calibrated and still unequal in its errors, and why both sides were right.
Studios:
- ml/studios/studio-01-churn.html · S1 (after Part 1) · Frame a Churn Prediction Problem: From 'reduce churn' to a target, a prediction window, a metric, a baseline and an action.
- ml/studios/studio-02-fraud.html · S2 (after Part 4) · Design a Fraud Detection Model: Rare positives, delayed labels, adversaries and a review queue with limited capacity.
- ml/studios/studio-03-forecasting.html · S3 (after Part 5) · Design Demand Forecasting for a Retailer: Thousands of products, promotions, stockouts and the decision the forecast feeds.
Toolbox (ml/toolbox.html#id):
- #sklearn · scikit-learn · chapters 04,05,06,07,10,11,13: The reference library for classical ML, with a consistent fit/predict interface.
- #gbdt · XGBoost, LightGBM & CatBoost · chapters 09,17,20: The three boosted-tree libraries that dominate tabular problems.
- #shap · SHAP · chapters 16: Per-prediction feature attributions, and plots to read them with care.
- #tracking · MLflow & Weights & Biases · chapters 13,21: Log every run's parameters, metrics and artefacts so results can be compared and reproduced.
- #kaggle · Kaggle · chapters 20: Competitions, datasets, notebooks with free GPUs, and the forums where winners explain themselves.
- #evidently · Drift monitoring tools · chapters 21: Compare live data with training data and alert on shifts.

## A2 · Deep Learning & Transformers  (id "dl", folder deep-learning/)

Part 0: Orientation
- deep-learning/chapters/00-start-here.html · ch 00 · intro · Start Here: What deep learning is, what changed in 2012 and 2017, and the road to building a GPT.
Part 1: Neural Networks
- deep-learning/chapters/01-neurons-layers.html · ch 01 · deep · Neurons, Layers & Activations: Weighted sums, non-linearities, layers and why depth helps.
- deep-learning/chapters/02-backpropagation.html · ch 02 · deep · Backpropagation Through a Network: The chain rule applied to whole layers: matrix gradients, by hand and in code.
- deep-learning/chapters/03-training-dynamics.html · ch 03 · deep · Initialisation, Normalisation & Residuals: Vanishing and exploding signals, careful initialisation, LayerNorm and skip connections.
- deep-learning/chapters/04-deep-regularisation.html · ch 04 · core · Regularising Deep Networks: Weight decay, dropout, data augmentation, early stopping and the strange case of double descent.
- deep-learning/chapters/05-pytorch.html · ch 05 · core · PyTorch as an Autodiff Engine: Tensors, autograd, modules, optimisers and the standard training loop.
Part 2: Representation
- deep-learning/chapters/06-embeddings.html · ch 06 · deep · Embeddings: Words as Vectors: One-hot to dense vectors, word2vec, and why meaning becomes geometry.
- deep-learning/chapters/07-convolutions.html · ch 07 · core · Convolutions & Images: Filters, weight sharing, pooling and the ideas from vision that carried over.
- deep-learning/chapters/08-sequences-rnns.html · ch 08 · core · Sequences & Recurrent Networks: RNNs and LSTMs, the bottleneck of a single hidden state, and why they gave way to attention.
Part 3: Attention & the Transformer
- deep-learning/chapters/09-attention.html · ch 09 · deep · Attention from First Principles: Queries, keys and values, scaled dot products, softmax weights, masking and multiple heads.
- deep-learning/chapters/10-transformer-block.html · ch 10 · deep · The Transformer Block: Attention, MLPs, residual streams and normalisation, assembled and explained.
- deep-learning/chapters/11-positions.html · ch 11 · core · Positional Information: Why attention needs positions: learned, sinusoidal, relative and rotary (RoPE) encodings.
- deep-learning/chapters/12-building-gpt.html · ch 12 · deep · Building a GPT: A decoder-only Transformer, end to end, trained on characters and read line by line.
Part 4: Tokens & Language Modelling
- deep-learning/chapters/13-tokenisation.html · ch 13 · deep · Tokenisation: Characters, bytes and byte-pair encoding, vocabulary size, and the bugs tokenisers cause.
- deep-learning/chapters/14-language-modelling.html · ch 14 · deep · The Language-Modelling Objective: Next-token prediction, cross-entropy, perplexity and what a model learns from it.
- deep-learning/chapters/15-decoding.html · ch 15 · core · Decoding Strategies: Greedy, temperature, top-k, top-p, beam search and constrained decoding.
Part 5: Training at Scale
- deep-learning/chapters/16-resource-accounting.html · ch 16 · deep · Parameters, FLOPs & Memory: Counting a model's parameters, the 6ND rule, activation memory and what fits on a GPU.
- deep-learning/chapters/17-training-stability.html · ch 17 · core · Mixed Precision & Training Stability: bf16 training, loss spikes, gradient clipping, learning-rate warmup and what logs to watch.
- deep-learning/chapters/18-scaling-laws.html · ch 18 · core · Scaling Laws: Loss as a power law of compute, data and parameters, and the compute-optimal recipe.
Part 6: Modern Architectures
- deep-learning/chapters/19-efficient-attention.html · ch 19 · core · Efficient Attention: Multi-query and grouped-query attention, sliding windows and FlashAttention's memory trick.
- deep-learning/chapters/20-mixture-of-experts.html · ch 20 · intro · Mixture of Experts: Routing tokens to a few of many experts: more parameters for the same compute, and the catches.
- deep-learning/chapters/21-vision-language.html · ch 21 · core · Vision-Language Models: Patches, image encoders, projectors and how a language model learns to read a picture.
- deep-learning/chapters/22-beyond-attention.html · ch 22 · intro · Beyond Attention: State-space models, linear attention and hybrids, and what they trade away.
Labs:
- deep-learning/labs/lab-01-mlp.html · L1 (after Part 1) · A Neural Network from Scratch: Matrix ops, a two-layer network, backprop by hand and a training loop on a toy dataset.
- deep-learning/labs/lab-02-embeddings.html · L2 (after Part 2) · Word Embeddings: Skip-gram with negative sampling on a small corpus, then nearest neighbours and analogies.
- deep-learning/labs/lab-03-attention.html · L3 (after Part 3) · Attention & a Transformer Block: Scaled dot-product attention, causal masks, multi-head attention and a block, checked shape by shape.
- deep-learning/labs/lab-04-tiny-gpt.html · L4 (after Part 3) · Train a Tiny GPT: A character-level GPT in pure Python, trained until it invents plausible names.
- deep-learning/labs/lab-05-tokeniser.html · L5 (after Part 4) · A BPE Tokeniser & Decoders: Train byte-pair encoding, round-trip any text, then implement greedy, top-k and top-p sampling.
- deep-learning/labs/lab-06-resources.html · L6 (after Part 5) · The Model Resource Calculator: Parameters, FLOPs, memory and compute-optimal sizes for real published models.
Cases:
- deep-learning/cases/case-01-alexnet.html · C1 · AlexNet and ImageNet, 2012 [Data + compute + method]: Two GPUs, a big labelled dataset and ReLUs: the result that restarted neural networks.
- deep-learning/cases/case-02-transformer.html · C2 · Attention Is All You Need [Parallel sequence models]: The 2017 translation paper whose architecture now runs nearly every frontier model.
- deep-learning/cases/case-03-gpt-scaling.html · C3 · From GPT-2 to GPT-3 [Scale changes behaviour]: A language model that learned tasks nobody trained it for, and the in-context learning surprise.
- deep-learning/cases/case-04-chinchilla.html · C4 · Chinchilla: Compute-Optimal Training [Balance data and size]: Why a smaller model trained on more tokens beat a model four times its size.
- deep-learning/cases/case-05-flashattention.html · C5 · FlashAttention [IO-aware algorithms]: Same maths, far less memory traffic: an exact attention kernel that changed context lengths.
- deep-learning/cases/case-06-glitch-tokens.html · C6 · SolidGoldMagikarp: Glitch Tokens [Tokeniser-model mismatch]: Tokens that existed in the vocabulary but almost never in training, and the odd behaviour they caused.
- deep-learning/cases/case-07-opt-logbook.html · C7 · Training OPT-175B: The Logbook [Operating a training run]: A public diary of restarts, loss spikes and hardware failures in a large training run.
Studios:
- deep-learning/studios/studio-01-debug-training.html · S1 (after Part 5) · Debug a Training Run That Will Not Learn: Flat loss, then a spike, then NaNs: find the causes in order, with the evidence for each.
- deep-learning/studios/studio-02-small-model-plan.html · S2 (after Part 6) · Plan a Small Model on a Budget: Pick size, tokens, context length and architecture for a domain model with a fixed GPU budget.
Toolbox (deep-learning/toolbox.html#id):
- #pytorch · PyTorch · chapters 05,12: The deep-learning framework this course's chapters use, from tensors to training loops.
- #nanogpt · nanoGPT, nanochat & minGPT · chapters 12,14,16: Karpathy's small, readable GPT implementations to train and modify.
- #tokenisers · Tokeniser playgrounds · chapters 13: See exactly how text becomes tokens, and compare tokenisers side by side.
- #tensorboard · TensorBoard & W&B · chapters 03,17: Watch loss, gradients and activations while a model trains.
- #profiler · PyTorch profiler · chapters 16,19: Find where the time and memory of a training step actually go.
- #colab · Free GPU notebooks · chapters 05,12: Run the chapters' PyTorch code on a free GPU when your laptop is too slow.

## A3 · Training, Post-training & Serving LLMs  (id "llm", folder llm-training/)

Part 0: Orientation
- llm-training/chapters/00-start-here.html · ch 00 · intro · Start Here: Base models, chat models and reasoning models, and the stages that make each.
Part 1: Pretraining Systems
- llm-training/chapters/01-pretraining-data.html · ch 01 · deep · Pretraining Data: Crawling, extracting, filtering, deduplicating and mixing trillions of tokens.
- llm-training/chapters/02-gpu-memory.html · ch 02 · deep · GPU Memory & Why Training Runs Out of It: Weights, gradients, optimiser state and activations, and the tricks that trade compute for memory.
- llm-training/chapters/03-parallelism.html · ch 03 · core · Parallel Training: Data, tensor, pipeline and sequence parallelism, ZeRO and FSDP, and the communication each costs.
- llm-training/chapters/04-kernels.html · ch 04 · intro · Kernels & Performance: Why a fused kernel beats three small ones, and a first look at Triton.
- llm-training/chapters/05-long-runs.html · ch 05 · core · Checkpoints, Failures & Long Runs: Hardware failures, checkpointing, restarts and monitoring a run that lasts for weeks.
Part 2: Reinforcement Learning Foundations
- llm-training/chapters/06-bandits-mdps.html · ch 06 · core · Bandits & Markov Decision Processes: Rewards, exploration versus exploitation, states, actions, returns and discounting.
- llm-training/chapters/07-policy-gradients.html · ch 07 · deep · Policy Gradients: REINFORCE derived step by step, baselines and why variance is the enemy.
- llm-training/chapters/08-ppo.html · ch 08 · deep · PPO & KL Penalties: Clipped objectives, trust regions and the KL leash that keeps a fine-tuned model sane.
- llm-training/chapters/09-value-functions.html · ch 09 · core · Value Functions & Advantage: Critics, temporal-difference learning and generalised advantage estimation.
Part 3: Post-training
- llm-training/chapters/10-sft.html · ch 10 · deep · Supervised Fine-Tuning: Instruction data, chat templates, loss masking, data quality and catastrophic forgetting.
- llm-training/chapters/11-lora.html · ch 11 · deep · LoRA, QLoRA & Parameter-Efficient Tuning: Low-rank updates, why they work, rank and alpha, and fine-tuning in 4-bit.
- llm-training/chapters/12-preference-optimisation.html · ch 12 · deep · Preference Optimisation: RLHF & DPO: Learning from comparisons: the RLHF pipeline, the DPO derivation and their relatives.
- llm-training/chapters/13-reward-models.html · ch 13 · core · Reward Models & Reward Hacking: Training reward models, over-optimisation, sycophancy and Goodhart's law in practice.
- llm-training/chapters/14-rlvr-grpo.html · ch 14 · deep · RL with Verifiable Rewards & GRPO: Checkable rewards, group-relative advantages and how reasoning models are trained.
- llm-training/chapters/15-distillation.html · ch 15 · core · Distillation & Synthetic Data: Teaching small models with big ones, logit distillation, synthetic data and model collapse.
Part 4: Cheap Adaptation
- llm-training/chapters/16-model-merging.html · ch 16 · core · Model Merging & Evolutionary Merging: Averaging weights, task vectors, TIES and DARE, and searching for merge recipes by evolution.
- llm-training/chapters/17-adapters-on-demand.html · ch 17 · intro · Adapters on Demand: Self-adaptive models and hypernetworks that generate adapters from a task description.
Part 5: Inference
- llm-training/chapters/18-kv-cache.html · ch 18 · deep · The KV Cache & the Cost of Decoding: Prefill versus decode, why generation is memory-bound, and what the cache costs.
- llm-training/chapters/19-quantisation.html · ch 19 · core · Quantisation: int8, int4 and fp8, per-channel scales, outliers, GPTQ and AWQ, and measuring the damage.
- llm-training/chapters/20-serving-engines.html · ch 20 · deep · Serving Engines: Continuous batching, paged attention, prefix caching and how vLLM and SGLang work.
- llm-training/chapters/21-speculative-decoding.html · ch 21 · intro · Speculative Decoding & Other Speedups: Draft and verify, Medusa-style heads, and why the output is unchanged.
- llm-training/chapters/22-token-economics.html · ch 22 · core · The Economics of a Token: Throughput, latency, batch size and price: what a million tokens costs to serve.
Part 6: Judging Models
- llm-training/chapters/23-evaluating-models.html · ch 23 · core · Evaluating a Model You Trained: Held-out sets, evaluation harnesses, contamination checks and regressions on other skills.
Labs:
- llm-training/labs/lab-01-data-pipeline.html · L1 (after Part 1) · A Pretraining Data Pipeline: Extract, filter by quality heuristics and deduplicate with MinHash and locality-sensitive hashing.
- llm-training/labs/lab-02-policy-gradient.html · L2 (after Part 2) · Policy Gradients & PPO: REINFORCE with a baseline, then PPO's clipped objective with a KL penalty, on bandits and a gridworld.
- llm-training/labs/lab-03-lora.html · L3 (after Part 3) · LoRA from Scratch: Freeze a small model, train low-rank adapters, merge them back and compare parameter counts.
- llm-training/labs/lab-04-dpo-grpo.html · L4 (after Part 3) · DPO & GRPO on a Toy Policy: Implement both losses on a policy over answers to arithmetic questions with a verifiable reward.
- llm-training/labs/lab-05-evolutionary-merge.html · L5 (after Part 4) · Evolutionary Model Merging: Merge task-specialised small models and evolve merge coefficients against a held-out task.
- llm-training/labs/lab-06-serving-sim.html · L6 (after Part 5) · A Serving Simulator: Simulate static and continuous batching with a paged KV cache, and measure throughput and latency.
- llm-training/labs/lab-07-quantisation.html · L7 (after Part 5) · Quantise a Model: Symmetric and asymmetric int8 and int4, per-channel scales and outlier handling, with error measured.
Cases:
- llm-training/cases/case-01-instructgpt.html · C1 · InstructGPT: RLHF in Practice [Learning from human preferences]: A smaller model that labellers preferred to one a hundred times larger.
- llm-training/cases/case-02-deepseek-r1.html · C2 · DeepSeek-R1 [RL with verifiable rewards]: Reasoning that emerged from reinforcement learning on checkable problems, then distilled into small models.
- llm-training/cases/case-03-llama3-training.html · C3 · Training Llama 3 at Scale [Reliability of training clusters]: Thousands of GPUs, hundreds of interruptions and the engineering that kept the run on track.
- llm-training/cases/case-04-vllm.html · C4 · vLLM and PagedAttention [Virtual memory for the KV cache]: Borrowing operating-system paging to stop wasting most of a GPU's cache memory.
- llm-training/cases/case-05-evolutionary-merge.html · C5 · Evolving Model Merges [Search over recipes]: Evolutionary search that combined existing open models into new capabilities without gradient training.
- llm-training/cases/case-06-sycophancy-rollback.html · C6 · The Sycophancy Rollback [Reward signals with side effects]: A model update that became too eager to please, and what its developer said went wrong.
- llm-training/cases/case-07-alpaca.html · C7 · Alpaca & Self-Instruct [Distillation from a stronger model]: Fifty-two thousand generated instructions, a few hundred dollars and a lesson about imitation.
Studios:
- llm-training/studios/studio-01-domain-adaptation.html · S1 (after Part 3) · Adapt a Model for a Specialist Domain: Prompting, retrieval, fine-tuning or all three, under a fixed budget, with the evaluation that decides.
- llm-training/studios/studio-02-reasoning-model.html · S2 (after Part 3) · Post-train a Small Reasoning Model: Pick the base model, reward, data and compute, and plan how you will catch reward hacking.
- llm-training/studios/studio-03-serving-platform.html · S3 (after Part 5) · Design an LLM Serving Platform: Many models, many tenants, latency targets and a GPU bill: batching, routing, caching and autoscaling.
Toolbox (llm-training/toolbox.html#id):
- #hf · Hugging Face transformers, TRL & PEFT · chapters 10,11,12,14: Load models, fine-tune with LoRA and run SFT, DPO and GRPO trainers.
- #unsloth · Unsloth · chapters 11,14: Memory-efficient fine-tuning and RL that fits on a single consumer or free GPU.
- #vllm · vLLM & SGLang · chapters 18,20,22: High-throughput open-source serving engines.
- #llamacpp · llama.cpp & Ollama · chapters 19: Run quantised models locally on a laptop CPU or GPU.
- #lm-eval · lm-evaluation-harness · chapters 23: Run standard benchmarks on any model the same way every time.
- #nvidia-smi · nvidia-smi & nvtop · chapters 02,05: See GPU memory, utilisation and temperature while something runs.

## A4 · Agents, Tools & Protocols  (id "agt", folder agents/)

Part 0: Orientation
- agents/chapters/00-start-here.html · ch 00 · intro · Start Here: Workflows versus agents, why agents fail, and the shape of this course.
Part 1: The Loop
- agents/chapters/01-model-apis.html · ch 01 · core · Talking to a Model: Messages and roles, system prompts, parameters, streaming and structured output.
- agents/chapters/02-tool-loop.html · ch 02 · deep · Tool Calling: The Agent Loop: Tool definitions, tool_use and tool_result turns, stop conditions and iteration budgets.
- agents/chapters/03-reasoning-planning.html · ch 03 · core · Reasoning, ReAct & Planning: Thought-action-observation, plan-then-execute, reflection and what reasoning models change.
- agents/chapters/04-prompting.html · ch 04 · core · Prompting as Programming: Clear instructions, examples, delimiters and prompts you can test, version and review.
Part 2: Tools & Protocols
- agents/chapters/05-tool-design.html · ch 05 · deep · Designing Tools for Agents: The agent-computer interface: names, descriptions, arguments, errors and output size.
- agents/chapters/06-function-calling.html · ch 06 · core · Function Calling Across Providers: JSON Schema contracts, parallel calls, forced tools and a provider-neutral adapter.
- agents/chapters/07-mcp.html · ch 07 · deep · MCP from the Wire Up: JSON-RPC messages, tools, resources and prompts, and a server written by hand.
- agents/chapters/08-mcp-production.html · ch 08 · core · MCP in Production: Transports, authorisation, versions and the stateless redesign, and how to survive spec changes.
- agents/chapters/09-agent-to-agent.html · ch 09 · core · Agent-to-Agent Protocols: Agent cards, tasks and delegation with A2A, and when agents should talk to agents at all.
Part 3: Context & Memory
- agents/chapters/10-context-engineering.html · ch 10 · deep · Context Engineering: Context as a budget: selection, compaction, just-in-time retrieval and context rot.
- agents/chapters/11-memory.html · ch 11 · core · Memory: Notes, Retrieval & Skills: Scratchpads, notes files, episodic and semantic memory, and libraries of reusable skills.
- agents/chapters/12-long-context.html · ch 12 · core · Long Context versus Retrieval: When to put everything in the window, when to retrieve, and how to measure the difference.
Part 4: Workflows & Teams
- agents/chapters/13-workflow-patterns.html · ch 13 · deep · Workflow Patterns: Chaining, routing, parallelising, orchestrator-workers and evaluator-optimiser loops as plain code.
- agents/chapters/14-multi-agent.html · ch 14 · deep · Multi-Agent Systems: Orchestrators and sub-agents, token costs, coordination failures and when one agent is better.
- agents/chapters/15-durable-execution.html · ch 15 · deep · Durable Execution for Agents: Event logs, checkpoints, idempotent side effects, resumption and human approval gates.
Part 5: Foundational Agents
- agents/chapters/16-deep-research.html · ch 16 · deep · Deep Research Agents: Planning, parallel search, reading, cross-checking, citing and synthesising a long report.
- agents/chapters/17-computer-use.html · ch 17 · deep · Computer-Use & Browser Agents: Screenshots versus accessibility trees, coordinates, actions, verification and safety.
- agents/chapters/18-coding-agents.html · ch 18 · core · Coding Agents: How SWE-agent, OpenHands and terminal coding agents read, edit, run and test code.
Part 6: Security & Engineering
- agents/chapters/19-agent-security.html · ch 19 · deep · Agent Security: Prompt injection, tool poisoning, data exfiltration and the lethal trifecta.
- agents/chapters/20-sandboxing.html · ch 20 · core · Sandboxes & Permissions: Containers, virtual machines, network allow-lists, least privilege and confirmation prompts.
- agents/chapters/21-frameworks.html · ch 21 · core · Agent Frameworks: What frameworks give you, what they hide, and how to choose one you can leave.
- agents/chapters/22-ai-coding-tools.html · ch 22 · deep · Working with AI Coding Tools: Instruction files, plans, verification loops, review and measuring whether it actually helps.
Labs:
- agents/labs/lab-01-agent-loop.html · L1 (after Part 1) · The Agent Loop from Scratch: Messages, tool schemas and a tool-calling loop with budgets, logging and a scripted fake model.
- agents/labs/lab-02-tool-design.html · L2 (after Part 2) · Tool Design, Measured: Two designs of the same toolset, a twenty-task evaluation and the numbers that pick the winner.
- agents/labs/lab-03-mcp.html · L3 (after Part 2) · An MCP Server & Client: JSON-RPC over stdio: initialise, list and call tools, resources and errors, both sides by hand.
- agents/labs/lab-04-workflows.html · L4 (after Part 4) · Workflow Patterns & Budgets: Chains, routers, parallel fan-out and orchestrator-workers, with token accounting for each.
- agents/labs/lab-05-durable-agent.html · L5 (after Part 4) · A Durable Agent: An event-sourced agent that survives being killed mid-task without repeating side effects.
- agents/labs/lab-06-deep-research.html · L6 (after Part 5) · A Mini Deep-Research Agent: Plan, search a local corpus, read, cite and verify every claim against its source.
- agents/labs/lab-07-injection.html · L7 (after Part 6) · Attack & Defend a Tool-Using Agent: Plant injections in documents and tool output, then measure which defences actually hold.
Cases:
- agents/cases/case-01-multi-agent-research.html · C1 · A Multi-Agent Research System [Orchestrator-workers]: Anthropic's write-up of a lead agent spawning researchers, and what token usage explained.
- agents/cases/case-02-swe-agent.html · C2 · SWE-agent and the Agent-Computer Interface [Tools shaped for models]: Why a purpose-built file viewer and editor beat a raw shell for a coding agent.
- agents/cases/case-03-metr-rct.html · C3 · Measuring AI Coding Productivity [Measure, don't assume]: A randomised trial in which experienced developers were slower with AI and believed they were faster.
- agents/cases/case-04-mcp-evolution.html · C4 · How MCP Changed, 2024 to 2026 [Protocols evolve]: From a local stdio protocol to remote servers, OAuth and a stateless redesign.
- agents/cases/case-05-injection-wild.html · C5 · Prompt Injection in the Wild [Untrusted input as instructions]: Exfiltration through assistants and MCP servers: real incidents and the common thread.
- agents/cases/case-06-replit-database.html · C6 · The Agent That Deleted Production [Least privilege for agents]: A coding agent with production access, a code freeze it ignored, and the safeguards added afterwards.
- agents/cases/case-07-computer-use.html · C7 · Teaching Models to Use Computers [Pixels as an interface]: Screenshot-driven agents, the OSWorld benchmark and why progress is measured in steps.
Studios:
- agents/studios/studio-01-support-agent.html · S1 (after Part 4) · Design a Customer-Support Agent: Answers, account lookups and refunds with limits, escalation to humans and an audit trail.
- agents/studios/studio-02-research-product.html · S2 (after Part 5) · Design a Deep-Research Product: Long-running research jobs with citations, cost controls, progress updates and quality checks.
- agents/studios/studio-03-regulated-agent.html · S3 (after Part 6) · Design an Agent for a Regulated Back Office: Documents in, decisions out, with a threat model, approvals and evidence an auditor accepts.
Toolbox (agents/toolbox.html#id):
- #coding-agents · Claude Code, Codex CLI & Cursor · chapters 18,22: Terminal and editor coding agents, and how to configure them for a repository.
- #mcp-inspector · MCP Inspector · chapters 07,08: Connect to any MCP server and call its tools by hand.
- #sdks · Provider SDKs & agent SDKs · chapters 01,02,06,21: Official client libraries and agent SDKs, and what they do for you.
- #llm-cli · The llm command-line tool · chapters 01,04: Prompt many models from a terminal and log every response to SQLite.
- #playwright · Playwright · chapters 17: Drive a real browser from code: the substrate of many browser agents.
- #containers · Docker sandboxes · chapters 20,18: Give an agent a disposable machine with only the access it needs.

## A5 · Retrieval, Search & Document AI  (id "ret", folder retrieval/)

Part 0: Orientation
- retrieval/chapters/00-start-here.html · ch 00 · intro · Start Here: Search, retrieval and RAG, and the documents they have to cope with.
Part 1: Lexical Search
- retrieval/chapters/01-text-analysis.html · ch 01 · core · Text Analysis: Tokenising, normalising, stemming and analysers, and why index and query must agree.
- retrieval/chapters/02-bm25.html · ch 02 · deep · Inverted Indexes & BM25: Postings, term frequency, document frequency and length normalisation, derived and tuned.
- retrieval/chapters/03-query-understanding.html · ch 03 · core · Query Understanding: Spelling correction, synonyms, expansion, intent and the long tail of queries.
Part 2: Measuring Retrieval
- retrieval/chapters/04-relevance-metrics.html · ch 04 · deep · Relevance Metrics: Precision, recall, MRR, MAP and nDCG: what each rewards and which question it answers.
- retrieval/chapters/05-test-collections.html · ch 05 · deep · Building a Test Collection: Queries, judgements, pooling and guidelines: a gold set you can trust in a week.
- retrieval/chapters/06-retrieval-benchmarks.html · ch 06 · core · Public Benchmarks & Their Limits: BEIR, MTEB and domain benchmarks as shortlist filters, not decisions.
Part 3: Dense Retrieval
- retrieval/chapters/07-dense-retrieval.html · ch 07 · deep · Dense Retrieval: Bi-encoders, contrastive training, hard negatives and fine-tuning an embedder.
- retrieval/chapters/08-rerankers.html · ch 08 · core · Rerankers: Cross-encoders and LLM rerankers: precision at the top for a price.
- retrieval/chapters/09-late-interaction-sparse.html · ch 09 · core · Late Interaction & Learned Sparse: ColBERT's token-level matching and SPLADE's learned term weights.
- retrieval/chapters/10-hybrid-search.html · ch 10 · deep · Hybrid Search & Rank Fusion: Combining lexical and dense results with reciprocal rank fusion and score normalisation.
Part 4: Vector Indexes
- retrieval/chapters/11-ann-indexes.html · ch 11 · deep · Approximate Nearest-Neighbour Search: HNSW, IVF and product quantisation, and the recall, latency and memory triangle.
- retrieval/chapters/12-filters-permissions.html · ch 12 · core · Filters, Metadata & Permissions: Pre- and post-filtering, tenant isolation and document-level access control in retrieval.
Part 5: The RAG System
- retrieval/chapters/13-rag-end-to-end.html · ch 13 · deep · RAG End to End: Ingest, index, retrieve, assemble, generate and cite: the whole pipeline and its knobs.
- retrieval/chapters/14-chunking.html · ch 14 · deep · Chunking & Contextual Retrieval: Fixed, structural and semantic chunks, chunk context, and parent-child retrieval.
- retrieval/chapters/15-agentic-retrieval.html · ch 15 · core · Query Rewriting, Agentic Retrieval & GraphRAG: Decomposing questions, iterative search, knowledge graphs and when each pays off.
- retrieval/chapters/16-grounded-citations.html · ch 16 · deep · Grounded Answers & Citations: Making every claim traceable to a span, and checking that the span supports it.
- retrieval/chapters/17-rag-failures.html · ch 17 · deep · How RAG Fails: Missed retrieval, wrong chunk, ignored context, stale sources and confident synthesis.
Part 6: Document AI
- retrieval/chapters/18-pdf-layout.html · ch 18 · deep · PDFs & Layout: What a PDF really contains, born-digital versus scanned, reading order and layout analysis.
- retrieval/chapters/19-ocr.html · ch 19 · deep · OCR: Classical Engines to Vision-Language Models: Detection and recognition, Tesseract to VLM-based OCR, error rates and hallucinated text.
- retrieval/chapters/20-tables-forms.html · ch 20 · core · Tables, Forms & Key-Value Extraction: Table structure recognition, form fields, schemas and validating extracted values.
- retrieval/chapters/21-visual-retrieval.html · ch 21 · core · Visual Document Retrieval: Embedding page images directly with ColPali-style models, and when that beats OCR.
- retrieval/chapters/22-multilingual.html · ch 22 · intro · Multilingual & Multi-Script Documents: Scripts without spaces, mixed languages, right-to-left text and cross-lingual retrieval.
Labs:
- retrieval/labs/lab-01-bm25.html · L1 (after Part 1) · A Search Engine with BM25: An analyser, an inverted index, BM25 scoring and top-k retrieval, tested on a small corpus.
- retrieval/labs/lab-02-retrieval-eval.html · L2 (after Part 2) · A Retrieval Evaluation Harness: Precision, recall, MRR and nDCG from judgements, with confidence intervals and a paired comparison.
- retrieval/labs/lab-03-hybrid.html · L3 (after Part 3) · Hybrid Retrieval & Reranking: Dense vectors, BM25, reciprocal rank fusion and a reranker, each measured with your harness.
- retrieval/labs/lab-04-hnsw.html · L4 (after Part 4) · HNSW from Scratch: Build a hierarchical navigable small-world graph and chart recall against search effort.
- retrieval/labs/lab-05-rag-citations.html · L5 (after Part 5) · RAG with Verified Citations: Chunk, retrieve, answer with citations and reject any answer whose quotes are not in the source.
- retrieval/labs/lab-06-document-pipeline.html · L6 (after Part 6) · A Document Understanding Pipeline: From OCR boxes to reading order, sections and tables, with character error rate measured.
Cases:
- retrieval/cases/case-01-contextual-retrieval.html · C1 · Contextual Retrieval [Context before embedding]: Prepending chunk context, hybrid search and reranking, and the failure rates each step removed.
- retrieval/cases/case-02-bert-search.html · C2 · BERT Comes to Web Search [Understanding queries]: When a search engine started reading the little words in queries.
- retrieval/cases/case-03-lost-in-the-middle.html · C3 · Lost in the Middle [Long context is not free]: Models that used evidence at the start and end of the context and missed it in the middle.
- retrieval/cases/case-04-air-canada.html · C4 · The Chatbot's Promise: Air Canada [Grounded answers are a liability question]: A tribunal held an airline to a refund policy its chatbot made up.
- retrieval/cases/case-05-faiss.html · C5 · FAISS: Billion-Scale Similarity Search [Compressed vectors]: Product quantisation and GPU search that made nearest neighbours over billions of vectors practical.
- retrieval/cases/case-06-colpali.html · C6 · ColPali: Retrieving Pages as Images [Skip the OCR]: Embedding page screenshots directly, and a benchmark built to test it.
- retrieval/cases/case-07-open-document-parsers.html · C7 · Open Document Conversion Pipelines [Layout models + OCR]: How Docling and olmOCR turn PDFs into structured text, and how they were evaluated.
Studios:
- retrieval/studios/studio-01-enterprise-search.html · S1 (after Part 4) · Design Enterprise Search with Permissions: Many sources, per-document access control, freshness and relevance across a whole company.
- retrieval/studios/studio-02-policy-assistant.html · S2 (after Part 5) · Design a Policy & Regulation Assistant: Answers people will act on, from a corpus that changes, with citations a reviewer can check.
- retrieval/studios/studio-03-document-processing.html · S3 (after Part 6) · Design a Document-Processing Pipeline: Millions of scanned forms and invoices a month, with extraction accuracy and human review.
Toolbox (retrieval/toolbox.html#id):
- #opensearch · Elasticsearch & OpenSearch · chapters 01,02,10: The standard open-source search engines, with BM25, analysers and vector search.
- #vector-dbs · pgvector, Qdrant & friends · chapters 11,12: Vector indexes inside Postgres or as dedicated databases.
- #sbert · sentence-transformers · chapters 07,08: Load, run and fine-tune embedding models and cross-encoders.
- #ir-eval · ranx & pytrec_eval · chapters 04,05: Standard implementations of retrieval metrics to check your own against.
- #docling · Docling, Marker & MinerU · chapters 18,20: Open-source PDF-to-structure converters.
- #ocr · Tesseract & PaddleOCR · chapters 19,22: Classical and deep-learning OCR engines you can run locally.

## A6 · Evals, Guardrails & Safe Operation  (id "evl", folder evals/)

Part 0: Orientation
- evals/chapters/00-start-here.html · ch 00 · intro · Start Here: Evaluation as the core skill of AI engineering, and the loop this course teaches.
Part 1: Measurement
- evals/chapters/01-error-analysis.html · ch 01 · deep · Error Analysis: Reading traces, open and axial coding, the first failure in each trace, and failure taxonomies.
- evals/chapters/02-eval-harnesses.html · ch 02 · deep · Assertions & Eval Harnesses: Deterministic checks first, test cases as data, and a harness you can run on every change.
- evals/chapters/03-llm-judges.html · ch 03 · deep · LLM-as-Judge: Binary rubrics, pairwise comparisons, position and length bias, and calibrating judges against people.
- evals/chapters/04-eval-statistics.html · ch 04 · deep · Statistics for Evals: Error bars, paired comparisons, clustered questions, sample sizes and repeated runs.
- evals/chapters/05-human-labels.html · ch 05 · core · Human Labels: Guidelines, inter-annotator agreement, adjudication and running a labelling effort.
Part 2: Benchmarks
- evals/chapters/06-building-benchmarks.html · ch 06 · deep · Building a Domain Benchmark: Task definition, sourcing items, gold answers, difficulty, data cards and versioning.
- evals/chapters/07-contamination.html · ch 07 · deep · Contamination, Saturation & Decay: How benchmarks leak into training data, saturate, and get audited and retired.
- evals/chapters/08-agent-evals.html · ch 08 · deep · Evaluating Agents: End-state checks, trajectory review, simulated users, pass@k versus pass^k, and cost per task.
- evals/chapters/09-leaderboards.html · ch 09 · core · Reading Leaderboards Critically: Arena ratings, self-reported scores, scaffolds and the questions to ask of any number.
Part 3: Truthfulness
- evals/chapters/10-hallucination.html · ch 10 · core · Why Models Hallucinate: Kinds of hallucination, their causes in training and scoring, and how to measure them.
- evals/chapters/11-grounding-abstention.html · ch 11 · deep · Grounding, Abstention & Confidence: Answering only from evidence, saying 'I don't know', and risk-coverage curves.
- evals/chapters/12-fact-checking.html · ch 12 · deep · Fact-Checking & Citation Verification: Claim extraction, evidence retrieval, entailment checks and verifying that citations support claims.
Part 4: Adversaries
- evals/chapters/13-prompt-injection.html · ch 13 · deep · Prompt Injection & Jailbreaks: Direct and indirect injection, jailbreak families, and why detection loses to adaptive attackers.
- evals/chapters/14-architectural-defences.html · ch 14 · deep · Architectural Defences: Capability limits, the rule of two, dual-model patterns and CaMeL-style data-flow control.
- evals/chapters/15-guardrails.html · ch 15 · core · Guardrail Classifiers & Content Policy: Input and output classifiers, policy design, PII filters and measuring guardrail recall.
- evals/chapters/16-red-teaming.html · ch 16 · core · Red Teaming: Planning, manual and automated attacks, scoring findings and closing the loop.
Part 5: Operations
- evals/chapters/17-observability.html · ch 17 · core · Tracing & Observability for LLM Systems: Spans for model and tool calls, what to log, sampling, and OpenTelemetry's GenAI conventions.
- evals/chapters/18-improvement-flywheel.html · ch 18 · deep · The Improvement Flywheel: Production traces to labelled failures to regression suites to safer releases.
- evals/chapters/19-cost-latency-quality.html · ch 19 · core · Cost, Latency & Quality Trade-offs: Pareto fronts, model routing, caching and deciding what 'good enough' costs.
- evals/chapters/20-ai-incidents.html · ch 20 · intro · AI Incident Response: Detecting, containing and learning from an AI system that misbehaves in production.
Part 6: Governance
- evals/chapters/21-governance.html · ch 21 · core · Governance Frameworks & Regulation: NIST AI RMF, ISO/IEC 42001 and the EU AI Act, read as engineering requirements.
- evals/chapters/22-privacy-data.html · ch 22 · core · Privacy & Data Handling for AI: PII in prompts and logs, retention, training on customer data, and data residency.
Labs:
- evals/labs/lab-01-eval-harness.html · L1 (after Part 1) · An Eval Harness with Error Bars: Run cases, score them, bootstrap confidence intervals and compare two systems with a paired test.
- evals/labs/lab-02-judge-calibration.html · L2 (after Part 1) · Calibrate an LLM Judge: Measure a judge's agreement with human labels, probe position and length bias, and correct the estimate.
- evals/labs/lab-03-benchmark.html · L3 (after Part 2) · Build a Domain Benchmark: Validate items, split them, version them and run a contamination probe.
- evals/labs/lab-04-agent-eval.html · L4 (after Part 2) · Evaluate an Agent: A simulated shop with a database: grade end states, run each task k times and report pass^k.
- evals/labs/lab-05-citations-abstention.html · L5 (after Part 3) · Citation Checking & Abstention: Verify quoted spans, score claim support, then sweep an abstention threshold on a risk-coverage curve.
- evals/labs/lab-06-red-team.html · L6 (after Part 4) · Red-Team a RAG Agent: Forty injection payloads against four defences, with attack success rates and utility costs.
- evals/labs/lab-07-regression-gate.html · L7 (after Part 5) · Traces & a Regression Gate: Emit spans, turn failures into regression cases and block a release that gets worse.
Cases:
- evals/cases/case-01-swe-bench-verified.html · C1 · Retiring SWE-bench Verified [Benchmark lifecycle]: A widely reported coding benchmark, an audit of its hardest tasks, and why its main sponsor stopped using it.
- evals/cases/case-02-cuda-engineer.html · C2 · The AI CUDA Engineer [Evaluator hacking]: Claimed kernel speedups that came from loopholes in the evaluation harness.
- evals/cases/case-03-mata-avianca.html · C3 · Fake Citations in Court [Unverified generation]: Lawyers who filed a brief citing cases a chatbot had invented, and the court's response.
- evals/cases/case-04-attacker-moves-second.html · C4 · The Attacker Moves Second [Adaptive attacks]: Published prompt-injection defences re-tested against attackers who adapt, and what survived.
- evals/cases/case-05-tau-bench.html · C5 · tau-bench: Agents with Simulated Users [End-state grading]: Grading an agent by the database it leaves behind, and reliability measured as pass^k.
- evals/cases/case-06-leaderboard-illusion.html · C6 · The Leaderboard Illusion [Rankings can be gamed]: Private testing, selective disclosure and sampling rates behind a popular model arena.
- evals/cases/case-07-ai-overviews.html · C7 · Glue on Pizza: Search Answers Go Wrong [Bad sources, confident answers]: AI-generated search summaries that repeated jokes and satire as fact, and the fixes that followed.
Studios:
- evals/studios/studio-01-eval-program.html · S1 (after Part 2) · Design the Eval Program for an Assistant: Who labels, what is measured, how often, which numbers block a release and who signs off.
- evals/studios/studio-02-agent-guardrails.html · S2 (after Part 4) · Design Guardrails for an Agent with Tools: An agent that reads email and can send it: threat model, capability limits, classifiers and monitoring.
- evals/studios/studio-03-llm-observability.html · S3 (after Part 5) · Design LLM Observability & Continuous Evaluation: Traces at scale, online evaluators, sampling, dashboards, alerts and the path from failure to fix.
Toolbox (evals/toolbox.html#id):
- #inspect · Inspect · chapters 02,06,08: The UK AI Security Institute's open-source evaluation framework.
- #promptfoo · promptfoo · chapters 02,16: Declarative test cases, assertions and red-team scans for prompts and apps.
- #tracing · Langfuse & Phoenix · chapters 17,18: Open-source tracing, datasets and online evaluation for LLM applications.
- #redteam · garak & PyRIT · chapters 13,16: Automated vulnerability scanners and red-teaming toolkits for language models.
- #labelling · Annotation tools · chapters 01,05: Spreadsheets, Label Studio and custom review apps for reading and labelling traces.
- #presidio · Presidio · chapters 15,22: Detect and redact personal data in text before it reaches a model or a log.

## A7 · Search, Evolution & Self-Improving Agents  (id "oe", folder open-ended/)

Part 0: Orientation
- open-ended/chapters/00-start-here.html · ch 00 · intro · Start Here: Objectives, search and open-ended discovery, and what this course builds.
Part 1: Search Foundations
- open-ended/chapters/01-tree-search.html · ch 01 · deep · Tree Search, Bandits & MCTS: Exploration versus exploitation, UCB, Monte Carlo tree search and the AlphaZero idea.
- open-ended/chapters/02-evolutionary-algorithms.html · ch 02 · deep · Evolutionary Algorithms: Populations, mutation, crossover, selection pressure and evolution strategies.
- open-ended/chapters/03-novelty-search.html · ch 03 · core · Why Objectives Deceive: Deceptive fitness landscapes, novelty search and the value of stepping stones.
- open-ended/chapters/04-quality-diversity.html · ch 04 · deep · Quality-Diversity & MAP-Elites: Archives of diverse high performers, behaviour descriptors and illumination.
Part 2: Open-Endedness
- open-ended/chapters/05-open-ended-algorithms.html · ch 05 · core · Open-Ended Algorithms: POET and co-evolving problems with solutions, and what 'open-ended' means.
- open-ended/chapters/06-interestingness.html · ch 06 · core · Models of Interestingness: Using foundation models to judge what is new and worth learning: OMNI and successors.
- open-ended/chapters/07-lifelong-agents.html · ch 07 · core · Lifelong Agents & Skill Libraries: Voyager's curriculum, skills as code and agents that accumulate abilities.
Part 3: LLMs as Search Operators
- open-ended/chapters/08-inference-time-search.html · ch 08 · deep · Inference-Time Search: Best-of-n, self-consistency, tree search over answers, verifiers and adaptive branching.
- open-ended/chapters/09-program-evolution.html · ch 09 · deep · LLM-Guided Program Evolution: FunSearch and AlphaEvolve: language models as mutation operators with automatic evaluators.
- open-ended/chapters/10-evolution-frameworks.html · ch 10 · core · Open Evolution Frameworks: Inside OpenEvolve and ShinkaEvolve: islands, archives, novelty rejection and sample efficiency.
- open-ended/chapters/11-evolving-prompts.html · ch 11 · core · Evolving Prompts & Pipelines: Prompt evolution, self-referential improvement and optimising LLM programs with DSPy.
Part 4: Meta Agents
- open-ended/chapters/12-meta-agent-search.html · ch 12 · deep · Automated Design of Agentic Systems: A meta agent that writes agents as code, keeps an archive and searches for better designs.
- open-ended/chapters/13-self-improving-agents.html · ch 13 · deep · Self-Improving Coding Agents: The Darwin Gödel Machine: an agent that edits its own scaffold, validated empirically.
- open-ended/chapters/14-automated-science.html · ch 14 · core · Automated Science: The AI Scientist: ideas, experiments, papers and automated review, and their limits.
Part 5: Integrity
- open-ended/chapters/15-evaluator-hacking.html · ch 15 · deep · Evaluator Hacking & Reward Hacking: Search finds every loophole in the scorer: famous examples and how to harden evaluators.
- open-ended/chapters/16-held-out-evaluation.html · ch 16 · deep · Held-Out Evaluation for Self-Improvers: Separate search, selection and test sets, and the statistics of picking the best of many.
- open-ended/chapters/17-self-modification-safety.html · ch 17 · core · Safety of Self-Modifying Systems: Sandboxes, lineage tracking, human oversight and objectives that resist gaming.
Part 6: Applied
- open-ended/chapters/18-search-in-products.html · ch 18 · core · Search Inside Real Products: Evolving prompts, rules and heuristics for a business, and when simpler methods win.
Labs:
- open-ended/labs/lab-01-mcts.html · L1 (after Part 1) · Bandits & Monte Carlo Tree Search: Epsilon-greedy, UCB and Thompson sampling, then MCTS that plays a small game well.
- open-ended/labs/lab-02-map-elites.html · L2 (after Part 1) · Novelty Search & MAP-Elites: A deceptive maze where objective search fails, novelty search succeeds and MAP-Elites illuminates.
- open-ended/labs/lab-03-program-evolution.html · L3 (after Part 3) · A Mini FunSearch: Evolve bin-packing heuristics as code with an island archive and a pluggable mutation operator.
- open-ended/labs/lab-04-ab-mcts.html · L4 (after Part 3) · Adaptive Branching over Many Models: Decide when to sample a new answer, refine an old one or switch models, under a call budget.
- open-ended/labs/lab-05-meta-agent.html · L5 (after Part 4) · A Mini Meta-Agent Search: Search over agent designs on a small benchmark, with separate search and held-out splits.
- open-ended/labs/lab-06-gameable-evaluator.html · L6 (after Part 5) · The Gameable Evaluator: Watch a search loop exploit a leaky scorer, then harden the harness until the exploits stop.
Cases:
- open-ended/cases/case-01-alphazero.html · C1 · AlphaGo to AlphaZero [Search plus learning]: Tree search guided by a learned policy and value, and what self-play removed.
- open-ended/cases/case-02-picbreeder.html · C2 · Picbreeder & Why Greatness Cannot Be Planned [Stepping stones]: Images nobody aimed for, found by people following what was interesting.
- open-ended/cases/case-03-funsearch.html · C3 · FunSearch and the Cap Set [Evolving programs, not answers]: A language model in an evolutionary loop that found new constructions in mathematics.
- open-ended/cases/case-04-alphaevolve.html · C4 · AlphaEvolve [Evolution with evaluators]: Evolving whole codebases against automatic evaluators, from matrix multiplication to data-centre scheduling.
- open-ended/cases/case-05-voyager.html · C5 · Voyager in Minecraft [Skill libraries]: A lifelong agent that wrote its own curriculum and kept its skills as code.
- open-ended/cases/case-06-darwin-godel-machine.html · C6 · The Darwin Gödel Machine [Open-ended self-improvement]: A coding agent that rewrote its own tools, and the objective hacking its authors reported.
- open-ended/cases/case-07-ai-scientist.html · C7 · The AI Scientist and Peer Review [Automating the research loop]: Generated papers, an automated reviewer and a workshop submission, read with care.
Studios:
- open-ended/studios/studio-01-optimisation-loop.html · S1 (after Part 3) · Design an Automated Optimisation Loop: Evolve a scheduling heuristic for a business: evaluator, budget, archive, safety and rollout.
- open-ended/studios/studio-02-review-claim.html · S2 (after Part 5) · Review a Self-Improvement Claim: A team says its agent improved itself by 30%. Decide what you need to see before you believe it.
Toolbox (open-ended/toolbox.html#id):
- #openevolve · OpenEvolve · chapters 09,10: An open-source implementation of AlphaEvolve-style program evolution.
- #shinka · ShinkaEvolve · chapters 10: Sakana AI's sample-efficient open-source evolution framework.
- #pyribs · pyribs · chapters 04: A quality-diversity library with MAP-Elites and its descendants.
- #dspy · DSPy · chapters 11: Write LLM pipelines as modules and let optimisers tune prompts and examples.
- #evotorch · Evolution-strategy libraries · chapters 02: CMA-ES and friends for black-box optimisation.

## A8 · Applied AI Delivery Studio  (id "aid", folder ai-delivery/)

Part 0: Orientation
- ai-delivery/chapters/00-start-here.html · ch 00 · intro · Start Here: The applied AI engineer's job, and how the studios in this capstone work.
Part 1: Discovery
- ai-delivery/chapters/01-discovery-interviews.html · ch 01 · deep · Discovery Interviews: Asking about past behaviour, not opinions; finding the real problem behind the requested feature.
- ai-delivery/chapters/02-requirements-ambiguity.html · ch 02 · deep · Requirements Under Ambiguity: Turning a vague goal into decisions, constraints and success metrics both sides sign.
- ai-delivery/chapters/03-expert-knowledge.html · ch 03 · deep · Capturing Expert Knowledge: Shadowing, think-aloud sessions and worked examples: turning tacit judgement into rubrics and data.
- ai-delivery/chapters/04-feasibility.html · ch 04 · core · Is AI the Right Tool?: Feasibility, error tolerance, data availability and risk: a triage before anyone builds.
Part 2: Building the Proof
- ai-delivery/chapters/05-riskiest-assumption.html · ch 05 · deep · Prototype the Riskiest Assumption: Build the smallest thing that could prove you wrong, in days, not months.
- ai-delivery/chapters/06-evaluation-plans.html · ch 06 · deep · Evaluation Plans Customers Trust: Gold sets from the customer's own work, agreed metrics and comparison with the current process.
- ai-delivery/chapters/07-choosing-models.html · ch 07 · core · Choosing Models: Frontier APIs, open-weight models and on-premises deployment, chosen by evidence and constraints.
Part 3: Domains
- ai-delivery/chapters/08-finance.html · ch 08 · core · Finance: Lending, research, compliance and wealth management, with model risk management and audit.
- ai-delivery/chapters/09-healthcare.html · ch 09 · core · Healthcare & Life Sciences: Clinical documentation, patient safety, medical-device rules and protected health data.
- ai-delivery/chapters/10-legal.html · ch 10 · core · Legal & Compliance: Contracts, discovery and research, privilege and confidentiality, and verifying every citation.
- ai-delivery/chapters/11-public-sector.html · ch 11 · core · Public Sector & Government: Citizen services, analysts and caseworkers, procurement, transparency and accountability.
Part 4: Delivery
- ai-delivery/chapters/12-poc-to-production.html · ch 12 · deep · From Proof of Concept to Production: Why most pilots stall, production gates, integration, support and change management.
- ai-delivery/chapters/13-restricted-environments.html · ch 13 · core · Restricted Environments: On-premises and air-gapped deployment, data residency and a limited menu of approved models.
- ai-delivery/chapters/14-cost-roi.html · ch 14 · core · Cost Models & Return on Investment: Unit economics per task, total cost of ownership and an honest return-on-investment case.
- ai-delivery/chapters/15-security-review.html · ch 15 · core · Security Reviews for AI Systems: The questions a customer's security team will ask, and the evidence pack that answers them.
Part 5: Productisation & Communication
- ai-delivery/chapters/16-research-to-product.html · ch 16 · core · Turning Research into Products: From a paper and a repository to an interface, SLOs, documentation and support.
- ai-delivery/chapters/17-writing-for-customers.html · ch 17 · deep · Writing for Customers: Status reports, analysis memos and presenting a failure honestly to the people paying.
- ai-delivery/chapters/18-getting-hired.html · ch 18 · deep · Take-Homes, Portfolios & Interviews: What applied AI teams test, how to scope a take-home, and a portfolio that proves judgement.
- ai-delivery/chapters/19-where-next.html · ch 19 · intro · Where Next: Keeping up without drowning, and the next steps after this path.
Labs:
- ai-delivery/labs/lab-01-brief-to-eval.html · L1 (after Part 2) · From Brief to Evaluation Kit: Turn a customer brief and sample documents into a validated gold set, rubric and acceptance thresholds.
- ai-delivery/labs/lab-02-cost-model.html · L2 (after Part 4) · A Cost & Latency Model: Price a workload across models, caching and batching, and find the cheapest option that meets the bar.
- ai-delivery/labs/lab-03-pii-pipeline.html · L3 (after Part 4) · A PII Redaction & Audit Pipeline: Detect and redact personal data, keep reversible tokens for authorised users and log every access.
- ai-delivery/labs/lab-04-take-home.html · L4 (after Part 5) · A Take-Home, End to End: A timed document-QA system graded by hidden tests, with the memo that goes with it.
Cases:
- ai-delivery/cases/case-01-klarna.html · C1 · Klarna's AI Assistant [Automation claims meet customers]: An assistant said to do the work of hundreds of agents, and the later decision to bring humans back.
- ai-delivery/cases/case-02-morgan-stanley.html · C2 · A Research Assistant for Financial Advisers [Evals before rollout]: An assistant over a firm's own research library, gated by an evaluation framework built with experts.
- ai-delivery/cases/case-03-nyc-mycity.html · C3 · A City's Chatbot Gives Illegal Advice [Public-sector accountability]: A government business-advice chatbot that told owners they could break the law.
- ai-delivery/cases/case-04-forward-deployed.html · C4 · The Forward-Deployed Engineer [Engineers embedded with customers]: How embedding engineers with customers became a model for AI companies.
- ai-delivery/cases/case-05-legal-ai-rollout.html · C5 · Rolling Out AI in a Law Firm [Expert users, verification culture]: Pilots, verification rules and adoption when every answer must be checked by a professional.
- ai-delivery/cases/case-06-bank-lending-workflow.html · C6 · An Expert Workflow for Bank Lending [Decompose expert reasoning]: A loan-document assistant built by structuring expert judgement, with feedback loops calibrated to reviewers.
Studios:
- ai-delivery/studios/studio-01-contract-review.html · S1 (after Part 2) · Take-Home: Contract Clause Review: A legal team wants risky clauses flagged in supplier contracts. Scope it, build the proof, report.
- ai-delivery/studios/studio-02-analyst-assistant.html · S2 (after Part 2) · Take-Home: An Analyst's Research Assistant: Answer questions over annual reports with numbers that tie to the page they came from.
- ai-delivery/studios/studio-03-claims-triage.html · S3 (after Part 3) · Take-Home: Insurance Claims Triage: Route incoming claims with attachments, and decide what never goes to a model.
- ai-delivery/studios/studio-04-citizen-services.html · S4 (after Part 3) · Take-Home: Citizen Services Q&A: A government help service that must be accurate, accessible and accountable.
- ai-delivery/studios/studio-05-clinical-notes.html · S5 (after Part 3) · Take-Home: Clinical Note Summaries: Summaries clinicians can trust, with omissions measured as carefully as errors.
- ai-delivery/studios/studio-06-support-automation.html · S6 (after Part 4) · Take-Home: Support Automation with Refunds: Automate part of a support queue with money at stake, and prove the savings.
- ai-delivery/studios/studio-07-coding-assistant-rollout.html · S7 (after Part 4) · Take-Home: Rolling Out a Coding Assistant: A 300-engineer company wants AI coding tools. Plan the rollout and measure the effect honestly.
- ai-delivery/studios/studio-08-productise-research.html · S8 (after Part 5) · Take-Home: Productise a Research Prototype: A promising research repository, a customer who wants it next quarter, and everything in between.
Toolbox (ai-delivery/toolbox.html#id):
- #demo-uis · Gradio & Streamlit · chapters 05: A usable demo in an afternoon, so customers react to something real.
- #fastapi · FastAPI · chapters 12,16: Typed Python web APIs with generated documentation.
- #compose · Docker Compose · chapters 13,12: Package a whole system so a customer can run it inside their own network.
- #pii-tools · Presidio for redaction · chapters 15,09: Detect and anonymise personal data before it leaves a boundary.
- #writing · Writing & diagram tools · chapters 17,18: Markdown, Mermaid and a memo template for status reports and analysis write-ups.
