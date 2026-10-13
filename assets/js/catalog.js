/* Single source of truth for every course on the site.
   The hub, sidebars, prev/next pagers, roadmaps, cross-links and progress
   tracking are all built from this file. Each course lives in its own folder
   (course.dir) with chapters/, labs/, cases/ and studios/ inside.

   To add a page: add an entry to the right course array, then create
   <course.dir>/<kind folder>/<file> with the matching data-* attribute on <body>.
   depth: "deep" | "core" | "intro". related: ids in this course ("05") or
   another course ("net:05"). Studios are interview-style design exercises. */

(function () {
  var NET_PARTS = [
    { title: "Orientation",                blurb: "The map before the journey." },
    { title: "Foundations: Moving Bits",    blurb: "How 1s and 0s physically travel, and how we organise the work into layers." },
    { title: "The Internet Layer",          blurb: "Addresses and routing: how a packet crosses the planet." },
    { title: "Transport",                   blurb: "Ports, UDP and TCP: turning a best-effort mess into reliable conversations." },
    { title: "Applications",                blurb: "DNS, HTTP, TLS and APIs: the protocols you actually touch every day." },
    { title: "Networks at Scale",           blurb: "Speed limits, latency budgets and the machines that sit in the middle." },
    { title: "Toward Distributed Systems",  blurb: "Many computers, one system: failure, time, replication and agreement." },
    { title: "Extensions",                  blurb: "Chapters added after a curriculum review, filling gaps that senior engineers meet in practice." }
  ];

  var NET_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",       title: "Start Here",                         blurb: "What a network is, and the journey of a single message." },

    { id: "01", part: 1, depth: "deep",  file: "01-bits-and-signals.html", title: "Bits, Bytes & Signals",              blurb: "Binary, wires, light, radio, and the crucial difference between bandwidth and latency." },
    { id: "02", part: 1, depth: "core",  file: "02-local-networks.html",   title: "Local Networks & Ethernet",          blurb: "Frames, MAC addresses, switches and Wi-Fi: talking to the computer next to you." },
    { id: "03", part: 1, depth: "deep",  file: "03-layers.html",           title: "Layers & Encapsulation",             blurb: "Envelopes inside envelopes: the single most useful mental model in networking." },

    { id: "04", part: 2, depth: "deep",  file: "04-ip-addresses.html",     title: "IP Addresses & Subnets",             blurb: "Addresses, binary, CIDR, private ranges, NAT and a peek at IPv6." },
    { id: "05", part: 2, depth: "deep",  file: "05-routing.html",          title: "Routing",                            blurb: "Routers, routing tables, hops and how the Internet stitches itself together." },
    { id: "06", part: 2, depth: "intro", file: "06-arp-dhcp-icmp.html",    title: "The Glue: ARP, DHCP & ICMP",         blurb: "Small helper protocols that make everything else work." },

    { id: "07", part: 3, depth: "core",  file: "07-ports-udp.html",        title: "Ports, Sockets & UDP",               blurb: "Which program gets the data, and the simplest way to send it." },
    { id: "08", part: 3, depth: "deep",  file: "08-tcp.html",              title: "TCP Deep Dive",                      blurb: "Handshakes, sequence numbers, retransmission, flow and congestion control." },

    { id: "09", part: 4, depth: "deep",  file: "09-dns.html",              title: "DNS: The Internet's Phonebook",      blurb: "Turning names into addresses with a giant, cached, distributed database." },
    { id: "10", part: 4, depth: "deep",  file: "10-http.html",             title: "HTTP & the Web",                     blurb: "Requests, responses, status codes, and what happens when you type a URL." },
    { id: "11", part: 4, depth: "core",  file: "11-tls.html",              title: "TLS & Security Basics",              blurb: "Encryption, keys, certificates and the padlock in your browser." },
    { id: "12", part: 4, depth: "core",  file: "12-apis.html",             title: "How Programs Talk: Sockets & APIs",  blurb: "Client/server, REST, RPC, WebSockets and serialization." },

    { id: "13", part: 5, depth: "deep",  file: "13-performance.html",      title: "Latency, Throughput & Performance",  blurb: "Numbers every engineer should know, and why the slowest request matters most." },
    { id: "14", part: 5, depth: "core",  file: "14-load-balancers.html",   title: "Proxies, Load Balancers & CDNs",     blurb: "The machines in the middle that make big websites possible." },

    { id: "15", part: 6, depth: "deep",  file: "15-why-distribute.html",   title: "Why Distribute? Partial Failure",    blurb: "Why we use many machines, and the 8 lies we tell ourselves about networks." },
    { id: "16", part: 6, depth: "deep",  file: "16-failure.html",          title: "Failure, Timeouts & Retries",        blurb: "Slow or dead? Retries, idempotency, delivery guarantees and the Two Generals." },
    { id: "17", part: 6, depth: "deep",  file: "17-time.html",             title: "Time, Clocks & Ordering",            blurb: "Why clocks lie, and how Lamport and vector clocks restore order." },
    { id: "18", part: 6, depth: "deep",  file: "18-replication.html",      title: "Replication & Consistency",          blurb: "Copies of data, quorums, consistency models and the CAP theorem." },
    { id: "19", part: 6, depth: "core",  file: "19-partitioning.html",     title: "Partitioning & Consistent Hashing",  blurb: "Splitting data across machines without reshuffling everything." },
    { id: "20", part: 6, depth: "deep",  file: "20-consensus.html",        title: "Consensus & Raft",                   blurb: "How a group of unreliable machines agrees on anything at all." },
    { id: "21", part: 6, depth: "intro", file: "21-where-next.html",       title: "Patterns & Where to Go Next",        blurb: "Queues, logs, sagas, circuit breakers, and a reading list." },

    { id: "22", part: 7, depth: "core",  file: "22-cloud-networking.html", title: "Cloud Networking",                   blurb: "VPCs, subnets, route tables, security groups, NAT and private endpoints: the network you rent from a cloud provider." }
  ];


  /* Hands-on labs: build the ideas in code. afterPart = the Part whose chapters
     you need first; related = chapter ids the lab uses. Files live in labs/. */
  var NET_LABS = [
    { id: "L1", file: "lab-01-sockets.html",        title: "Sockets & a Chat Server",       afterPart: 3, related: ["07", "08", "12"], blurb: "UDP echo, then a multi-client TCP chat server. Framing, ports and byte streams in practice." },
    { id: "L2", file: "lab-02-reliable-udp.html",   title: "Reliable Delivery over UDP",    afterPart: 3, related: ["07", "08"],       blurb: "Rebuild TCP's core: sequence numbers, ACKs, timeouts and a sliding window over a lossy link." },
    { id: "L3", file: "lab-03-dns-resolver.html",   title: "A DNS Resolver from Scratch",   afterPart: 4, related: ["09", "07"],       blurb: "Build DNS packets byte by byte, ask the root servers and follow referrals with a TTL cache." },
    { id: "L4", file: "lab-04-http-server.html",    title: "An HTTP Server from Scratch",   afterPart: 4, related: ["10", "12"],       blurb: "Parse requests, serve files, send status codes and headers, and support keep-alive." },
    { id: "L5", file: "lab-05-kv-store.html",       title: "A Replicated Key-Value Store",  afterPart: 6, related: ["16", "18"],       blurb: "Three nodes, quorum reads and writes, stale reads, retries with backoff and idempotency keys." },
    { id: "L6", file: "lab-06-raft.html",           title: "Toy Raft",                      afterPart: 6, related: ["17", "20"],       blurb: "Leader election and log replication in a deterministic simulation you can partition." }
  ];

  /* Case studies: real systems and incidents, each built around one pattern.
     related = chapter ids it draws on. Files live in cases/. */
  var NET_CASES = [
    { id: "C1",  file: "case-01-anycast.html",               title: "Anycast: One Address, Many Places",        pattern: "Anycast routing",                related: ["05", "09", "14"],       blurb: "How one IP address can live in hundreds of cities, and BGP sends you to the nearest." },
    { id: "C2",  file: "case-02-isp-caches.html",            title: "Caches Inside Your ISP",                   pattern: "Push content to the edge",       related: ["13", "14"],             blurb: "Why streaming services put their servers inside other companies' networks." },
    { id: "C3",  file: "case-03-dns-steering.html",          title: "Steering Traffic with DNS",                pattern: "DNS-based load balancing",       related: ["09", "14"],             blurb: "GeoDNS, short TTLs and failover, and why DNS is a coarse steering wheel." },
    { id: "C4",  file: "case-04-nat-traversal.html",         title: "Punching Through NAT",                     pattern: "NAT traversal",                  related: ["04", "07"],             blurb: "How two devices that are both behind NAT manage to talk directly: STUN, TURN, ICE." },
    { id: "C5",  file: "case-05-persistent-connections.html", title: "Millions of Open Connections",            pattern: "Connection gateways & fan-out",  related: ["08", "12", "14"],       blurb: "How chat apps keep a live connection to every user and deliver messages instantly." },
    { id: "C6",  file: "case-06-facebook-2021.html",         title: "When the Map Disappears: Facebook, 2021",  pattern: "Control-plane dependencies",     related: ["05", "09", "15"],       blurb: "A routine command withdrew Facebook's routes, its DNS vanished, and so did the tools to fix it." },
    { id: "C7",  file: "case-07-s3-2017.html",               title: "Small Mistake, Big Blast Radius: S3, 2017", pattern: "Blast radius & cells",          related: ["15", "16"],             blurb: "One mistyped input, a cold restart, and a lesson in containing failures." },
    { id: "C8",  file: "case-08-retry-storms.html",          title: "Retry Storms & Metastable Failures",       pattern: "Load shedding & backoff",        related: ["13", "16"],             blurb: "When the system stays down after the trigger is gone, and how to stop feeding the fire." },
    { id: "C9",  file: "case-09-dynamo.html",                title: "Dynamo: The Cart That Always Says Yes",    pattern: "Leaderless replication",         related: ["17", "18", "19"],       blurb: "Amazon's always-writable store: consistent hashing, sloppy quorums and vector clocks." },
    { id: "C10", file: "case-10-ordering-at-scale.html",     title: "Ordering at Scale: Spanner & the Log",     pattern: "Global order from clocks & logs", related: ["17", "18", "20", "21"], blurb: "Two ways to give the whole world one order of events: trusted clocks and a shared log." }
  ];


  /* Toolbox: real tools worth learning, each with a guided exercise on
     <course>/toolbox.html#<id>. chapters = where the "Tools to try" box shows it.
     linux: true = needs Linux (use the lab machine page for a VM). */
  var NET_TOOLS = [
    { id: "wireshark", name: "Wireshark",                 chapters: ["03", "07", "08", "09", "10", "11"], blurb: "See every packet and every layer of every header, decoded. The single best way to make this course real." },
    { id: "tcpdump",   name: "tcpdump",                   chapters: ["07", "08", "09"],                   blurb: "Wireshark's command-line cousin: capture packets in a terminal or on a remote server." },
    { id: "ping-mtr",  name: "ping, traceroute & mtr",    chapters: ["05", "06", "13", "22"],                   blurb: "Measure round-trip time and watch the routers your packets cross." },
    { id: "dig",       name: "dig",                       chapters: ["09", "22"],                               blurb: "Ask DNS servers anything and read their full answers, referrals and TTLs." },
    { id: "curl",      name: "curl",                      chapters: ["10", "11", "12"],                   blurb: "Speak HTTP by hand and see headers, redirects, TLS and timing." },
    { id: "nc",        name: "netcat (nc)",               chapters: ["07", "08", "12"],                   blurb: "Open raw TCP or UDP connections and type bytes straight into a socket." },
    { id: "openssl",   name: "openssl s_client",          chapters: ["11"],                               blurb: "Do a TLS handshake by hand and inspect a server's certificate chain." },
    { id: "ss-lsof",   name: "ss, netstat & lsof",        chapters: ["07", "08", "14"],                   blurb: "List open sockets, listening ports and connection states on your machine." },
    { id: "iperf3",    name: "iperf3",                    chapters: ["01", "13"],                         blurb: "Measure real throughput between two machines, and see bandwidth vs latency." }
  ];

  /* ---------- Course 1: How Programs Run ---------- */

  var SYS_PARTS = [
    { title: "Orientation",            blurb: "What really happens inside one machine when a request arrives." },
    { title: "The Machine",            blurb: "CPUs, memory and the ladder of speeds that shapes every program." },
    { title: "The Operating System",   blurb: "The kernel, processes, virtual memory, files, and what it takes for data to survive a crash." },
    { title: "Concurrency",            blurb: "Doing many things at once without corrupting your data: threads, races, locks and queues." },
    { title: "Talking to the World",   blurb: "Blocking and non-blocking I/O, event loops and async: how one machine serves thousands of connections." },
    { title: "Isolation",              blurb: "Containers and virtual machines, and the bridge to data systems." },
    { title: "Extensions",                  blurb: "Chapters added after a curriculum review, filling gaps that senior engineers meet in practice." }
  ];

  var SYS_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",       title: "Start Here",                          blurb: "One request's journey through a single machine, and the map of this course." },

    { id: "01", part: 1, depth: "core",  file: "01-cpu.html",              title: "CPUs & Instructions",                 blurb: "What a program really is, how a CPU runs it, and what cores and clock speed mean." },
    { id: "02", part: 1, depth: "deep",  file: "02-memory-hierarchy.html", title: "The Memory Hierarchy",                blurb: "Registers, caches, RAM, disk: the ladder of speeds, and why locality rules performance." },
    { id: "03", part: 1, depth: "core",  file: "03-stack-heap.html",       title: "Stack, Heap & Garbage Collection",    blurb: "Where a running program keeps its data, and who cleans up after it." },

    { id: "04", part: 2, depth: "deep",  file: "04-kernel-syscalls.html",  title: "The Kernel & System Calls",           blurb: "The referee between programs and hardware, and the doorway every program must knock on." },
    { id: "05", part: 2, depth: "deep",  file: "05-processes.html",        title: "Processes",                           blurb: "fork, exec, wait, signals and exit codes: how programs are born, run and die." },
    { id: "06", part: 2, depth: "deep",  file: "06-virtual-memory.html",   title: "Virtual Memory",                      blurb: "Every process gets its own private universe of addresses. Pages, page faults and the TLB." },
    { id: "07", part: 2, depth: "intro", file: "07-scheduling.html",       title: "Scheduling & Context Switches",       blurb: "How one CPU core takes turns between hundreds of programs, and what switching costs." },
    { id: "08", part: 2, depth: "core",  file: "08-files.html",            title: "Files & File Descriptors",            blurb: "Inodes, directories, permissions, and why a socket is \"just a file\" too." },
    { id: "09", part: 2, depth: "deep",  file: "09-durability.html",       title: "Durability: Written Is Not Saved",    blurb: "The page cache, fsync, atomic rename and journaling: what survives when the power goes out." },

    { id: "10", part: 3, depth: "core",  file: "10-threads.html",          title: "Threads",                             blurb: "Several flows of execution sharing one memory, and how they differ from processes." },
    { id: "11", part: 3, depth: "deep",  file: "11-race-conditions.html",  title: "Race Conditions",                     blurb: "Interleavings, lost updates and check-then-act: why counter += 1 is not one step." },
    { id: "12", part: 3, depth: "deep",  file: "12-locks.html",            title: "Locks, Atomics & Condition Variables", blurb: "Mutexes, compare-and-swap, semaphores and waiting politely for something to happen." },
    { id: "13", part: 3, depth: "core",  file: "13-deadlock.html",         title: "Deadlock, Livelock & Starvation",     blurb: "When threads wait for each other forever, and the simple rules that prevent it." },
    { id: "14", part: 3, depth: "deep",  file: "14-queues-backpressure.html", title: "Queues, Thread Pools & Backpressure", blurb: "Bounded queues, worker pools, Little's law and saying \"not now\" before you fall over." },

    { id: "15", part: 4, depth: "core",  file: "15-blocking-io.html",      title: "Blocking vs Non-blocking I/O",        blurb: "What happens when a program waits for the network or the disk, and how to stop waiting." },
    { id: "16", part: 4, depth: "deep",  file: "16-event-loops.html",      title: "Event Loops",                         blurb: "select, poll, epoll and kqueue: one thread juggling thousands of connections." },
    { id: "17", part: 4, depth: "core",  file: "17-async-await.html",      title: "Async/Await & Coroutines",            blurb: "Futures, coroutines and the golden rule: never block the loop." },
    { id: "18", part: 4, depth: "core",  file: "18-concurrency-models.html", title: "Concurrency Models Compared",        blurb: "Threads, events, actors and channels, and how real servers mix them." },

    { id: "19", part: 5, depth: "core",  file: "19-containers-vms.html",   title: "Containers & Virtual Machines",       blurb: "Hypervisors, namespaces and cgroups: what Docker actually does." },
    { id: "20", part: 5, depth: "intro", file: "20-where-next.html",       title: "Where Next: On to Data Systems",      blurb: "What you can now explain, and how it sets you up for databases." },

    { id: "21", part: 6, depth: "core",  file: "21-parallelism-gpus.html", title: "Parallelism, SIMD & GPUs",          blurb: "Amdahl's law, vector instructions, GPUs and memory bandwidth: why machine learning runs on accelerators." },
    { id: "22", part: 6, depth: "deep",  file: "22-performance-engineering.html", title: "Performance Engineering",    blurb: "A method for making programs faster: measure, profile on- and off-CPU, read flame graphs and benchmark honestly." }
  ];

  var SYS_LABS = [
    { id: "L1", file: "lab-01-shell.html",          title: "A Mini Shell",                  afterPart: 2, related: ["05", "08"],       blurb: "fork, exec and wait, then pipes, redirection and Ctrl-C. Build the program you type into." },
    { id: "L2", file: "lab-02-crash-safe-log.html", title: "Crash-Safe Storage",            afterPart: 2, related: ["08", "09"],       blurb: "An append-only log with checksums and fsync that recovers cleanly when killed mid-write." },
    { id: "L3", file: "lab-03-races-locks.html",    title: "Races & Locks",                 afterPart: 3, related: ["11", "12", "13"], blurb: "Reproduce a lost update, fix it, cause a deadlock, fix that, and build a blocking queue." },
    { id: "L4", file: "lab-04-thread-pool.html",    title: "A Thread Pool with Backpressure", afterPart: 3, related: ["10", "14"],     blurb: "Workers, futures, a bounded queue and rejection policies, measured under load." },
    { id: "L5", file: "lab-05-event-loop.html",     title: "Your Own Event Loop",           afterPart: 4, related: ["16", "17"],       blurb: "Callbacks and timers on selectors, then coroutines, serving a thousand connections on one thread." }
  ];

  var SYS_CASES = [
    { id: "C1", file: "case-01-fsyncgate.html",       title: "fsyncgate: When fsync Fails",              pattern: "Durability lies",              related: ["08", "09"],       blurb: "PostgreSQL trusted that a failed fsync could simply be retried. The kernel disagreed." },
    { id: "C2", file: "case-02-pathfinder.html",      title: "Priority Inversion on Mars",               pattern: "Priority inversion",           related: ["07", "12", "13"], blurb: "A spacecraft kept rebooting itself on Mars because a low-priority task held a lock." },
    { id: "C3", file: "case-03-leap-second.html",     title: "The Leap Second That Broke DNS",           pattern: "Wall clock vs monotonic clock", related: ["01", "04", "net:17"], blurb: "Time went backwards for one second, and a calculation that \"could never be negative\" was." },
    { id: "C4", file: "case-04-c10k-nginx.html",      title: "Ten Thousand Connections: nginx & C10k",   pattern: "Event-driven servers",         related: ["15", "16"],       blurb: "Why one thread per connection stopped scaling, and the event-driven design that replaced it." },
    { id: "C5", file: "case-05-redis.html",           title: "Redis: One Thread, Very Fast",             pattern: "Single-threaded event loop",   related: ["02", "16"],       blurb: "How a database serves huge request rates on a single thread, and where that design hurts." },
    { id: "C6", file: "case-06-discord-gc.html",      title: "Discord & the Garbage Collector",          pattern: "GC pauses & tail latency",     related: ["03", "net:13"],   blurb: "Periodic latency spikes, traced to garbage collection, and a rewrite in a language without one." },
    { id: "C7", file: "case-07-cloudflare-regex.html", title: "One Regex, Every CPU: Cloudflare 2019",   pattern: "CPU exhaustion & isolation",   related: ["01", "07"],       blurb: "A single regular expression consumed all CPU on machines worldwide. Why, and the safeguards since." },
    { id: "C8", file: "case-08-borg.html",            title: "Borg: Containers at Google Scale",         pattern: "Isolation & bin-packing",      related: ["06", "19"],       blurb: "How Google packs many jobs onto shared machines, and the ideas that became Kubernetes." }
  ];

  var SYS_STUDIOS = [
    { id: "S1", file: "studio-01-10k-connections.html", title: "Serve 10,000 Connections on One Machine", afterPart: 4, related: ["10", "14", "16"], blurb: "Threads or an event loop? Memory per connection, file-descriptor limits and where it breaks." },
    { id: "S2", file: "studio-02-log-shipper.html",     title: "A Log Shipper That Never Loses a Line",   afterPart: 4, related: ["09", "14", "16"], blurb: "Batching, fsync policy, a disk spool and backpressure, from crash to recovery." }
  ];

  var SYS_TOOLS = [
    { id: "top-htop",  name: "top & htop",                chapters: ["05", "07", "10"],                   blurb: "Watch processes, threads, CPU and memory live." },
    { id: "lsof",      name: "lsof",                      chapters: ["08", "15"],                         blurb: "See every file, pipe and socket a process has open." },
    { id: "strace",    name: "strace",                    chapters: ["04", "08", "16"], linux: true,      blurb: "Watch every system call a program makes, as it makes it." },
    { id: "proc",      name: "The /proc file system",     chapters: ["05", "06", "08"], linux: true,      blurb: "Read the kernel's view of any process: memory maps, open files, limits." },
    { id: "vmstat",    name: "vm_stat, vmstat & iostat",  chapters: ["06", "09"],                         blurb: "Memory pressure, paging and disk activity, system-wide." },
    { id: "hyperfine", name: "hyperfine",                 chapters: ["01", "02", "22"],                         blurb: "Benchmark commands properly: warm-ups, repeated runs and statistics." },
    { id: "py-spy",    name: "py-spy",                    chapters: ["03", "10", "17", "22"],                   blurb: "Sample a running Python program and see where its time goes, without changing it." },
    { id: "perf",      name: "perf & flame graphs",       chapters: ["01", "02", "07", "22", "21"], linux: true,      blurb: "Profile anything on Linux, down to cache misses, and draw it as a flame graph." },
    { id: "bpftrace",  name: "bpftrace",                  chapters: ["04", "09"], linux: true,            blurb: "Ask the running kernel questions with one-liners (advanced, but magical)." },
    { id: "unshare",   name: "unshare & Docker",          chapters: ["19"], linux: true,                  blurb: "Build a container by hand from namespaces, then compare with Docker." }
  ];

  /* ---------- Course 2: Data Systems ---------- */

  var DATA_PARTS = [
    { title: "Orientation",       blurb: "What a database actually does when you ask it a question." },
    { title: "Modelling Data",    blurb: "Tables, documents and graphs, and how data survives being sent and stored for years." },
    { title: "Storage Engines",   blurb: "Logs, LSM trees, B-trees and indexes: how a database lays bytes on disk and finds them again." },
    { title: "Transactions",      blurb: "ACID for real: isolation anomalies, MVCC, locking and recovering from crashes." },
    { title: "Data at Scale",     blurb: "Caches, replicas and shards: what happens when one database machine is not enough." },
    { title: "Data in Motion",    blurb: "Batch jobs, streams, change data capture, and how to choose a database." },
    { title: "Extensions",                  blurb: "Chapters added after a curriculum review, filling gaps that senior engineers meet in practice." }
  ];

  var DATA_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",        title: "Start Here",                          blurb: "The life of one query, from SQL text to bytes on disk and back." },

    { id: "01", part: 1, depth: "core",  file: "01-data-models.html",       title: "Data Models",                         blurb: "Relational, document, key-value, graph and wide-column: different shapes for different questions." },
    { id: "02", part: 1, depth: "core",  file: "02-sql-relational.html",    title: "SQL & the Relational Model",          blurb: "Tables, keys, joins and normalisation, and why SQL has lasted fifty years." },
    { id: "03", part: 1, depth: "core",  file: "03-encoding.html",          title: "Encoding & Schema Evolution",         blurb: "JSON, Protobuf and Avro, and changing your data's shape without breaking anyone." },

    { id: "04", part: 2, depth: "deep",  file: "04-log-hash-index.html",    title: "The Simplest Database: a Log",        blurb: "An append-only file plus an in-memory hash index, and the ideas every engine reuses." },
    { id: "05", part: 2, depth: "deep",  file: "05-lsm-trees.html",         title: "LSM Trees & SSTables",                blurb: "Memtables, sorted files, compaction and Bloom filters: storage built for fast writes." },
    { id: "06", part: 2, depth: "deep",  file: "06-b-trees.html",           title: "B-Trees",                             blurb: "Pages, splits, the buffer pool and the WAL: the structure behind most SQL databases." },
    { id: "07", part: 2, depth: "deep",  file: "07-indexes.html",           title: "Indexes",                             blurb: "Secondary, composite and covering indexes, and why the wrong index is worse than none." },
    { id: "08", part: 2, depth: "core",  file: "08-query-execution.html",   title: "Query Execution & Planning",          blurb: "Scans, joins and the planner's guesses: reading EXPLAIN like a pro." },
    { id: "09", part: 2, depth: "core",  file: "09-column-stores.html",     title: "Column Stores & Analytics",           blurb: "OLTP vs OLAP, columnar layout, compression and the data warehouse." },

    { id: "10", part: 3, depth: "deep",  file: "10-acid.html",              title: "Transactions & ACID",                 blurb: "What atomicity, consistency, isolation and durability really promise, and what they don't." },
    { id: "11", part: 3, depth: "deep",  file: "11-isolation.html",         title: "Isolation Levels & Anomalies",        blurb: "Dirty reads, lost updates, write skew and phantoms, and which isolation level stops which." },
    { id: "12", part: 3, depth: "deep",  file: "12-mvcc-locking.html",      title: "Implementing Isolation: 2PL, MVCC & SSI", blurb: "Locks versus versions: how databases actually keep transactions apart." },
    { id: "13", part: 3, depth: "core",  file: "13-crash-recovery.html",    title: "Crash Recovery",                      blurb: "Write-ahead logs, checkpoints and redo/undo: coming back from a crash with nothing lost." },

    { id: "14", part: 4, depth: "deep",  file: "14-caching.html",           title: "Caching",                             blurb: "Cache-aside, write-through, invalidation, TTLs, stampedes and hot keys." },
    { id: "15", part: 4, depth: "deep",  file: "15-replication-practice.html", title: "Replication in Practice",          blurb: "Leaders, followers, replication lag and its anomalies, and failing over without losing data." },
    { id: "16", part: 4, depth: "core",  file: "16-sharding.html",          title: "Sharding in Practice",                blurb: "Choosing a shard key, hot spots, cross-shard queries and rebalancing." },
    { id: "17", part: 4, depth: "intro", file: "17-specialised-stores.html", title: "Search & Specialised Stores",        blurb: "Inverted indexes, time-series and vector databases, and when to reach for them." },

    { id: "18", part: 5, depth: "core",  file: "18-batch.html",             title: "Batch Processing",                    blurb: "From Unix pipes to MapReduce and dataflow engines: processing all the data at once." },
    { id: "19", part: 5, depth: "deep",  file: "19-streams-cdc.html",       title: "Streams, Logs & Change Data Capture", blurb: "Event logs, consumers, CDC and the outbox pattern: keeping many systems in sync." },
    { id: "20", part: 5, depth: "intro", file: "20-choosing.html",          title: "Choosing a Database & Where Next",    blurb: "A practical way to pick storage for a workload, and the road to architecture." },

    { id: "21", part: 6, depth: "core",  file: "21-data-platforms.html", title: "Data Platforms: Warehouses, Lakehouses & Pipelines", blurb: "Open table formats, ELT, orchestration, data quality and lineage: how analytics data is moved and trusted." }
  ];

  var DATA_LABS = [
    { id: "L1", file: "lab-01-bitcask.html",       title: "A Log-Structured Key-Value Store", afterPart: 2, related: ["04", "sys:09"],  blurb: "An append-only log with an in-memory hash index, crash recovery and compaction." },
    { id: "L2", file: "lab-02-lsm.html",           title: "An LSM Tree",                   afterPart: 2, related: ["05"],              blurb: "Memtable, SSTable flushes, merge compaction and a Bloom filter that skips files." },
    { id: "L3", file: "lab-03-btree.html",         title: "A B-Tree",                      afterPart: 2, related: ["06", "07"],        blurb: "Search, insert with node splits and range scans, then count the pages you touch." },
    { id: "L4", file: "lab-04-slow-query.html",    title: "Make a Slow Query Fast",        afterPart: 2, related: ["07", "08"],        blurb: "SQLite, a million rows and EXPLAIN QUERY PLAN: indexes, covering indexes and query rewrites." },
    { id: "L5", file: "lab-05-mvcc.html",          title: "Snapshot Isolation from Scratch", afterPart: 3, related: ["11", "12"],      blurb: "A multi-version store with snapshots and write conflicts, then catch write skew." },
    { id: "L6", file: "lab-06-outbox-cdc.html",    title: "The Outbox & Change Data Capture", afterPart: 5, related: ["14", "19"],     blurb: "Keep a cache and a search index in sync with SQLite using an outbox and idempotent consumers." }
  ];

  var DATA_CASES = [
    { id: "C1", file: "case-01-github-failover.html", title: "43 Seconds That Took a Day: GitHub, 2018", pattern: "Failover & split brain",      related: ["15", "net:18"],   blurb: "A brief network partition, an automatic database failover, and writes in two data centers." },
    { id: "C2", file: "case-02-discord-messages.html", title: "Storing Trillions of Messages: Discord",  pattern: "Partition keys & hot spots",  related: ["05", "16"],       blurb: "From MongoDB to Cassandra to ScyllaDB, and the hot partitions that shaped each move." },
    { id: "C3", file: "case-03-memcache-facebook.html", title: "Scaling Memcache at Facebook",           pattern: "Look-aside caching at scale", related: ["14", "15"],       blurb: "Leases against stampedes and stale sets, regions and invalidation through the database log." },
    { id: "C4", file: "case-04-uber-postgres.html",   title: "Why Uber Moved from Postgres to MySQL",     pattern: "Storage-engine trade-offs",   related: ["06", "12", "15"], blurb: "Write amplification, MVCC and physical replication: how engine internals drove a migration." },
    { id: "C5", file: "case-05-gitlab-2017.html",     title: "The Backups That Weren't: GitLab, 2017",    pattern: "Backups you have tested",     related: ["13", "15"],       blurb: "A tired engineer, the wrong server, and backup methods that did not work when they were needed." },
    { id: "C6", file: "case-06-figma-sharding.html",  title: "Sharding Postgres at Figma",                pattern: "Horizontal sharding",         related: ["16", "07"],       blurb: "From one database to vertical partitions to horizontal shards behind a query proxy." },
    { id: "C7", file: "case-07-stripe-migrations.html", title: "Online Migrations at Stripe",            pattern: "Dual writes & backfills",     related: ["03", "19"],       blurb: "Moving live data to a new model in four phases without downtime." },
    { id: "C8", file: "case-08-aurora.html",          title: "Aurora: The Log Is the Database",           pattern: "Disaggregated storage",       related: ["13", "15", "06"], blurb: "Amazon's database that ships only redo log records to storage, and why that changes everything." }
  ];

  var DATA_STUDIOS = [
    { id: "S1", file: "studio-01-url-shortener.html", title: "Design a URL Shortener's Storage", afterPart: 4, related: ["07", "14", "16"], blurb: "Key generation, the read path, caching and sharding for a billion short links." },
    { id: "S2", file: "studio-02-ledger.html",        title: "Design a Payments Ledger",         afterPart: 3, related: ["10", "11", "12"], blurb: "Balances that are never wrong: double-entry, isolation, idempotency and audits." }
  ];

  var DATA_TOOLS = [
    { id: "sqlite",   name: "sqlite3",                chapters: ["02", "07", "08", "10"], blurb: "A complete SQL database in one file, built into Python and macOS. Your everyday lab bench." },
    { id: "postgres", name: "PostgreSQL & psql",       chapters: ["02", "08", "11", "12", "15"], blurb: "The open-source workhorse: EXPLAIN ANALYZE, isolation levels and replication you can poke." },
    { id: "explain",  name: "EXPLAIN & EXPLAIN ANALYZE", chapters: ["07", "08"],         blurb: "Ask the planner what it will do, and what it actually did." },
    { id: "redis",    name: "redis-cli",               chapters: ["14", "19"],             blurb: "Talk to an in-memory key-value store: TTLs, eviction and streams." },
    { id: "duckdb",   name: "DuckDB",                  chapters: ["09", "18", "21"],             blurb: "An in-process column store: run analytics over CSV and Parquet files in milliseconds." },
    { id: "pgbench",  name: "pgbench",                 chapters: ["10", "13"],             blurb: "Benchmark Postgres and watch fsync and group commit change throughput." },
    { id: "jq",       name: "jq",                      chapters: ["03", "19"],             blurb: "Slice and reshape JSON on the command line." }
  ];


  /* ---------- Course 3: Software Architecture & Design ---------- */

  var ARCH_PARTS = [
    { title: "Orientation",                blurb: "What architecture is, and why it is mostly about decisions that are hard to change." },
    { title: "Managing Complexity",        blurb: "Why software rots, and the module-level ideas that keep it understandable." },
    { title: "Structuring an Application", blurb: "Layers, ports and adapters, domain-driven design and testability." },
    { title: "APIs & Contracts",           blurb: "Designing interfaces other people depend on, and changing them without breaking anyone." },
    { title: "Monolith to Services",       blurb: "Monoliths, modular monoliths and microservices: where to draw boundaries and how parts talk." },
    { title: "Events & Workflows",         blurb: "Event-driven systems, sagas, CQRS and event sourcing." },
    { title: "Resilience & Evolution",     blurb: "Surviving failure, changing live systems safely, and recording why you decided what you did." },
    { title: "Extensions",                  blurb: "Chapters added after a curriculum review, filling gaps that senior engineers meet in practice." }
  ];

  var ARCH_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                           blurb: "What software architecture is, who does it, and how this course builds on the first three." },

    { id: "01", part: 1, depth: "deep",  file: "01-complexity.html",          title: "Complexity & Why Software Rots",       blurb: "Change amplification, cognitive load and unknown unknowns, and tactical versus strategic programming." },
    { id: "02", part: 1, depth: "deep",  file: "02-modules-coupling.html",    title: "Modules, Coupling & Cohesion",         blurb: "Deep modules, information hiding, and the kinds of coupling that make change expensive." },
    { id: "03", part: 1, depth: "core",  file: "03-abstractions.html",        title: "Abstractions & Interfaces",            blurb: "Designing interfaces, contracts and errors, and noticing when abstractions leak." },
    { id: "04", part: 1, depth: "core",  file: "04-design-patterns.html",     title: "Design Patterns That Matter",          blurb: "Strategy, adapter, facade, observer, decorator and dependency injection, and when not to use them." },

    { id: "05", part: 2, depth: "deep",  file: "05-hexagonal.html",           title: "Layers, Hexagonal & Clean Architecture", blurb: "Keeping business rules independent of databases, frameworks and the web: the dependency rule." },
    { id: "06", part: 2, depth: "core",  file: "06-ddd.html",                 title: "Domain-Driven Design Essentials",      blurb: "Ubiquitous language, bounded contexts, entities, value objects and aggregates." },
    { id: "07", part: 2, depth: "core",  file: "07-testability.html",         title: "Testability as Architecture",          blurb: "Seams, fakes and the test pyramid: designs that are easy to test are easy to change." },
    { id: "08", part: 2, depth: "intro", file: "08-cross-cutting.html",       title: "Cross-Cutting Concerns",               blurb: "Configuration, errors, logging, metrics and security: things every module touches." },

    { id: "09", part: 3, depth: "deep",  file: "09-api-design.html",          title: "API Design",                           blurb: "Resources, verbs, errors, pagination, idempotency keys, and REST versus RPC versus GraphQL." },
    { id: "10", part: 3, depth: "core",  file: "10-evolving-contracts.html",  title: "Evolving Contracts & Versioning",      blurb: "Compatibility rules, Hyrum's law, deprecation and versioning strategies." },

    { id: "11", part: 4, depth: "deep",  file: "11-monolith-microservices.html", title: "Monoliths, Modular Monoliths & Microservices", blurb: "The real trade-offs, Conway's law, and why most teams should start with a modular monolith." },
    { id: "12", part: 4, depth: "core",  file: "12-service-boundaries.html",  title: "Drawing Service Boundaries",           blurb: "Data ownership, database-per-service and the distributed-monolith trap." },
    { id: "13", part: 4, depth: "core",  file: "13-sync-async.html",          title: "Sync vs Async Communication",          blurb: "Request/response versus messaging, temporal coupling and the cost of every network hop." },

    { id: "14", part: 5, depth: "deep",  file: "14-event-driven.html",        title: "Event-Driven Architecture",            blurb: "Events versus commands, notification versus state transfer, and choreography's hidden costs." },
    { id: "15", part: 5, depth: "deep",  file: "15-sagas.html",               title: "Sagas & Distributed Workflows",        blurb: "Business transactions across services with compensations instead of rollbacks." },
    { id: "16", part: 5, depth: "core",  file: "16-cqrs-event-sourcing.html", title: "CQRS & Event Sourcing",                blurb: "Separate read and write models, and storing every change as an event." },

    { id: "17", part: 6, depth: "deep",  file: "17-resilience.html",          title: "Resilience Patterns",                  blurb: "Timeouts, retries, circuit breakers, bulkheads, rate limits and graceful degradation." },
    { id: "18", part: 6, depth: "core",  file: "18-evolving-safely.html",     title: "Evolving Systems Safely",              blurb: "Strangler fig, branch by abstraction, feature flags, expand/contract and canaries." },
    { id: "19", part: 6, depth: "core",  file: "19-documenting-decisions.html", title: "Documenting & Deciding",             blurb: "Architecture decision records, design docs, C4 diagrams and trade-off analysis." },
    { id: "20", part: 6, depth: "intro", file: "20-where-next.html",          title: "Where Next: On to Distributed Systems", blurb: "What you can now design, and the hard distributed problems still ahead." },

    { id: "21", part: 7, depth: "core",  file: "21-engineering-practice.html", title: "Engineering Practice at Scale", blurb: "Code review, continuous integration, trunk-based development, monorepos and build systems: how many engineers change one codebase safely." }
  ];

  var ARCH_LABS = [
    { id: "L1", file: "lab-01-hexagonal.html",     title: "Refactor to Hexagonal",                 afterPart: 2, related: ["05", "07"],       blurb: "Untangle a script that mixes SQL, HTTP and business rules into a core with ports and adapters." },
    { id: "L2", file: "lab-02-api.html",           title: "An Idempotent, Paginated, Versioned API", afterPart: 3, related: ["09", "10"],     blurb: "A small WSGI API with idempotency keys, cursor pagination, consistent errors and a v2 that breaks nobody." },
    { id: "L3", file: "lab-03-module-boundaries.html", title: "Enforce Module Boundaries",          afterPart: 4, related: ["02", "11", "12"], blurb: "Write an import checker, then split a monolith into modules that only talk through public interfaces." },
    { id: "L4", file: "lab-04-saga.html",          title: "A Saga Orchestrator",                   afterPart: 5, related: ["15", "data:19"],  blurb: "Order, payment, stock and shipping with compensations, idempotent steps and crash-safe resume." },
    { id: "L5", file: "lab-05-event-sourcing.html", title: "Event Sourcing & CQRS",                afterPart: 5, related: ["16", "14"],       blurb: "An event store, aggregates rebuilt from events, snapshots and projections for queries." },
    { id: "L6", file: "lab-06-resilience.html",    title: "A Resilience Toolkit",                  afterPart: 6, related: ["17", "net:16"],   blurb: "Timeouts, retries with jitter, a circuit breaker and a bulkhead, tested against a flaky fake." }
  ];

  var ARCH_CASES = [
    { id: "C1", file: "case-01-prime-video.html",  title: "Prime Video: Back to a Monolith",         pattern: "Right-sizing services",       related: ["11", "13"],       blurb: "A monitoring service rebuilt from distributed components into one process, and why that was the right call." },
    { id: "C2", file: "case-02-segment.html",      title: "Goodbye Microservices: Segment",          pattern: "When services multiply pain", related: ["11", "12"],       blurb: "Over a hundred destination services, shared libraries and queues, and the decision to consolidate." },
    { id: "C3", file: "case-03-shopify.html",      title: "Shopify's Modular Monolith",              pattern: "Modular monolith",            related: ["02", "11"],       blurb: "Keeping one huge codebase healthy with components, boundaries and tooling instead of services." },
    { id: "C4", file: "case-04-netflix-hystrix.html", title: "Netflix, Hystrix & Chaos",             pattern: "Circuit breakers & bulkheads", related: ["17", "13"],      blurb: "Isolating failing dependencies so one slow service cannot take down everything else." },
    { id: "C5", file: "case-05-stripe-versioning.html", title: "Stripe's API Versioning",             pattern: "Versioned contracts",         related: ["09", "10"],       blurb: "Keeping years of integrations working while the API keeps changing underneath." },
    { id: "C6", file: "case-06-uber-doma.html",    title: "Uber's Domain-Oriented Microservices",    pattern: "Domains & layers of services", related: ["06", "12"],      blurb: "Grouping thousands of services into domains with gateways and extension points." },
    { id: "C7", file: "case-07-knight-capital.html", title: "Knight Capital: 45 Minutes, $460 Million", pattern: "Dead code & unsafe deploys", related: ["18", "19"],     blurb: "A partial deployment, a repurposed flag and old code that came back to life." },
    { id: "C8", file: "case-08-lmax.html",         title: "LMAX: One Thread, Millions of Orders",     pattern: "In-memory event sourcing",    related: ["16", "sys:16"],   blurb: "A trading exchange built on a single-threaded business core fed by an input event log." }
  ];

  var ARCH_STUDIOS = [
    { id: "S1", file: "studio-01-food-delivery.html", title: "Design Food Delivery's Service Boundaries", afterPart: 5, related: ["06", "12", "15"], blurb: "Contexts, data ownership, sync versus async calls and the order saga for a delivery app." },
    { id: "S2", file: "studio-02-notifications.html", title: "Design a Notification Service",            afterPart: 6, related: ["09", "14", "17"], blurb: "Many channels, preferences, templates, rate limits, retries and never notifying twice." }
  ];

  var ARCH_TOOLS = [
    { id: "mermaid",   name: "Mermaid (diagrams as code)", chapters: ["00", "19"],       blurb: "Write architecture and sequence diagrams as text that lives next to your code." },
    { id: "openapi",   name: "OpenAPI",                    chapters: ["09", "10"],       blurb: "Describe an HTTP API in a machine-readable contract, then generate docs and checks from it." },
    { id: "import-graph", name: "Import graphs & boundary checkers", chapters: ["02", "05", "11", "21"], blurb: "See and enforce which modules may depend on which." },
    { id: "unittest",  name: "unittest & doubles",         chapters: ["07", "05", "21"],       blurb: "Python's built-in test framework, fakes and mocks: the tools of testable design." },
    { id: "adr",       name: "Architecture decision records", chapters: ["19"],          blurb: "A tiny, durable format for writing down why a decision was made." },
    { id: "load",      name: "HTTP load generators",       chapters: ["13", "17"],       blurb: "Push traffic at a service and watch timeouts, retries and circuit breakers behave." }
  ];


  /* ---------- Course 4: Distributed Systems, Deep ---------- */

  var DIST_PARTS = [
    { title: "Orientation",                 blurb: "What is still hard after replication and Raft, and how this course goes deeper." },
    { title: "Models & Failure",            blurb: "Precise models of time and failure, what is provably impossible, and noticing who is still alive." },
    { title: "Consistency",                 blurb: "Exactly what a system promises when many clients read and write at once." },
    { title: "Consensus",                   blurb: "Agreement under failure: Paxos, Raft in depth, coordination services and Byzantine faults." },
    { title: "Transactions Across Machines", blurb: "Atomic commit, real distributed databases, and the art of not coordinating at all." },
    { title: "Logs, Streams & Geography",   blurb: "The log as backbone, exactly-once processing, and systems that span continents." },
    { title: "Verification",                blurb: "Finding the bugs that only appear under rare interleavings: Jepsen, simulation and TLA+." }
  ];

  var DIST_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                            blurb: "What you already know from networking Part 6, what is still hard, and how this course goes deeper." },

    { id: "01", part: 1, depth: "deep",  file: "01-system-models.html",       title: "System Models: Time, Failure & Correctness", blurb: "Synchronous, asynchronous and partially synchronous systems; crash, omission and Byzantine faults; safety and liveness." },
    { id: "02", part: 1, depth: "core",  file: "02-impossibility.html",       title: "What Is Impossible: FLP, CAP & PACELC",  blurb: "Why consensus cannot be guaranteed in a purely asynchronous system, what CAP actually says, and the latency trade-off it leaves out." },
    { id: "03", part: 1, depth: "deep",  file: "03-failure-detection.html",   title: "Failure Detection, Membership & Gossip", blurb: "Heartbeats, phi-accrual detectors, SWIM and epidemic gossip: knowing who is alive without asking everyone." },
    { id: "04", part: 1, depth: "deep",  file: "04-leases-fencing.html",      title: "Leases, Locks & Fencing Tokens",         blurb: "Why a distributed lock is never quite a lock, how leases expire, and how fencing tokens make pauses safe." },

    { id: "05", part: 2, depth: "deep",  file: "05-consistency-models.html",  title: "Consistency Models, Precisely",          blurb: "Histories, linearizability, sequential and serializable consistency, and how to tell which one a system gives you." },
    { id: "06", part: 2, depth: "core",  file: "06-causal-session.html",      title: "Causal Consistency & Session Guarantees", blurb: "Read-your-writes, monotonic reads, causal order, and the strongest model that never blocks on a partition." },
    { id: "07", part: 2, depth: "core",  file: "07-time-revisited.html",      title: "Time Revisited: HLCs & TrueTime",        blurb: "Hybrid logical clocks, bounded clock uncertainty, commit wait, and when physical time can be trusted." },

    { id: "08", part: 3, depth: "deep",  file: "08-consensus-smr.html",       title: "Consensus & Replicated State Machines",  blurb: "The consensus problem, quorum intersection, total-order broadcast, and why one log can run any service." },
    { id: "09", part: 3, depth: "deep",  file: "09-paxos.html",               title: "Paxos, Step by Step",                    blurb: "Single-decree Paxos, why each phase exists, duelling proposers, and Multi-Paxos." },
    { id: "10", part: 3, depth: "deep",  file: "10-raft-deep.html",           title: "Raft in Depth",                          blurb: "The commitment rule's subtle case, membership changes, snapshots, linearizable reads and pre-vote." },
    { id: "11", part: 3, depth: "core",  file: "11-coordination-services.html", title: "Coordination Services: ZooKeeper & etcd", blurb: "Watches, ephemeral nodes, leader-election recipes, and what does not belong in a coordination service." },
    { id: "12", part: 3, depth: "intro", file: "12-byzantine.html",           title: "Byzantine Faults & Beyond",              blurb: "When nodes may lie: the 3f+1 bound, PBFT in outline, and where blockchains fit." },

    { id: "13", part: 4, depth: "deep",  file: "13-atomic-commit.html",       title: "Atomic Commit: 2PC & Its Limits",        blurb: "Two-phase commit, the blocking problem, presumed abort, and putting the coordinator on consensus." },
    { id: "14", part: 4, depth: "deep",  file: "14-distributed-transactions.html", title: "Distributed Transactions in Practice", blurb: "Percolator, Spanner and Calvin: three designs for serializable transactions across machines." },
    { id: "15", part: 4, depth: "deep",  file: "15-crdts.html",               title: "CRDTs: Data That Merges Itself",         blurb: "Join semilattices, state- and operation-based CRDTs, counters, sets, registers and collaborative text." },
    { id: "16", part: 4, depth: "core",  file: "16-coordination-avoidance.html", title: "Coordination Avoidance",              blurb: "Which invariants need coordination, the CALM theorem, escrow and bounded counters." },

    { id: "17", part: 5, depth: "deep",  file: "17-logs-exactly-once.html",   title: "Logs, Streams & Exactly-Once",           blurb: "Partitioned logs, in-sync replicas, consumer groups, and what exactly-once processing can really mean." },
    { id: "18", part: 5, depth: "core",  file: "18-multi-region.html",        title: "Multi-Region Systems",                   blurb: "Speed-of-light budgets, leader placement, active-active writes, conflict handling and failing over a region." },

    { id: "19", part: 6, depth: "deep",  file: "19-testing.html",             title: "Testing Distributed Systems",            blurb: "Fault injection, Jepsen-style history checking and deterministic simulation that replays any bug from a seed." },
    { id: "20", part: 6, depth: "core",  file: "20-formal-methods.html",      title: "Specifying with TLA+",                   blurb: "Writing a design as states and actions, checking invariants with a model checker, and when it is worth it." },
    { id: "21", part: 6, depth: "intro", file: "21-where-next.html",          title: "Where Next: On to Reliability",          blurb: "What you can now reason about, a reading list of the classic papers, and running systems for real." }
  ];

  var DIST_LABS = [
    { id: "L1", file: "lab-01-gossip.html",        title: "Gossip & Failure Detection",       afterPart: 1, related: ["03", "01"],        blurb: "A SWIM-style membership protocol in a simulated network with message loss, slow nodes and real crashes." },
    { id: "L2", file: "lab-02-fencing.html",       title: "Leases & Fencing Tokens",          afterPart: 1, related: ["04", "sys:03"],    blurb: "A lease-based lock service, a client that pauses at the worst moment, and storage that refuses stale writers." },
    { id: "L3", file: "lab-03-linearizability.html", title: "A Linearizability Checker",      afterPart: 2, related: ["05", "19"],        blurb: "Record concurrent histories and search for a legal order, then catch a store that serves stale reads." },
    { id: "L4", file: "lab-04-paxos.html",         title: "Multi-Paxos Replicated Log",       afterPart: 3, related: ["08", "09", "net:20"], blurb: "Paxos acceptors and proposers over a lossy, reordering network, then a replicated key-value store on top." },
    { id: "L5", file: "lab-05-two-phase-commit.html", title: "Two-Phase Commit & Recovery",   afterPart: 4, related: ["13", "data:10"],   blurb: "A coordinator and participants with write-ahead logs, crash recovery, presumed abort and the blocking window." },
    { id: "L6", file: "lab-06-crdts.html",         title: "CRDTs That Converge",              afterPart: 4, related: ["15", "16"],        blurb: "Counters, an observed-remove set and a register, proven to converge by randomized merge-order tests." },
    { id: "L7", file: "lab-07-simulation.html",    title: "Deterministic Simulation Testing", afterPart: 6, related: ["19", "05"],        blurb: "A seeded simulator that finds, replays and shrinks a hidden bug in a replicated store." }
  ];

  var DIST_CASES = [
    { id: "C1",  file: "case-01-chubby.html",        title: "Chubby: Google's Lock Service",          pattern: "Coarse-grained locks & sequencers", related: ["04", "11"],       blurb: "A Paxos-backed lock service that became Google's naming system, and why it chose coarse locks." },
    { id: "C2",  file: "case-02-zookeeper.html",     title: "ZooKeeper: Wait-Free Coordination",      pattern: "Coordination kernel",          related: ["11", "08"],       blurb: "Simple primitives, watches and ordering guarantees that let clients build their own locks and elections." },
    { id: "C3",  file: "case-03-redlock.html",       title: "The Redlock Debate",                     pattern: "Locks without fencing",        related: ["04", "01"],       blurb: "Two experts argue about a Redis locking algorithm, and what it teaches about timing assumptions." },
    { id: "C4",  file: "case-04-jepsen-etcd.html",   title: "Jepsen Tests etcd",                      pattern: "Testing the guarantees",       related: ["19", "05", "11"], blurb: "What an independent test of a Raft-based store found about reads, watches and locks." },
    { id: "C5",  file: "case-05-percolator.html",    title: "Percolator: Transactions on Bigtable",   pattern: "Snapshot isolation on a KV store", related: ["14", "13"],   blurb: "Incremental indexing at Google with client-driven two-phase commit and a timestamp oracle." },
    { id: "C6",  file: "case-06-cloudflare-partial-partition.html", title: "A Byzantine Failure in the Real World", pattern: "Partial partitions", related: ["03", "10", "12"], blurb: "A switch that dropped some traffic but not all, a confused Raft cluster and a long outage." },
    { id: "C7",  file: "case-07-kafka-exactly-once.html", title: "Kafka's Exactly-Once Semantics",    pattern: "Idempotence & transactions",   related: ["17", "13"],       blurb: "Idempotent producers, transactional writes and read-committed consumers, and what the guarantee covers." },
    { id: "C8",  file: "case-08-figma-multiplayer.html", title: "Figma's Multiplayer Engine",         pattern: "CRDT-inspired merging",        related: ["15", "06"],       blurb: "Real-time collaboration with a central server and per-property last-writer-wins, not a pure CRDT." },
    { id: "C9",  file: "case-09-foundationdb.html",  title: "FoundationDB: Simulation First",         pattern: "Deterministic simulation",     related: ["19", "14"],       blurb: "A database built so that its whole cluster can run, fail and be replayed inside one deterministic process." },
    { id: "C10", file: "case-10-aws-tla.html",       title: "Formal Methods at AWS",                  pattern: "Specifications that find bugs", related: ["20", "19"],      blurb: "Engineers using TLA+ on S3, DynamoDB and more, and the subtle bugs it found before production did." }
  ];

  var DIST_STUDIOS = [
    { id: "S1", file: "studio-01-lock-service.html",  title: "Design a Lock & Leader-Election Service", afterPart: 3, related: ["04", "10", "11"], blurb: "Leases, fencing, sessions and watches for thousands of clients, built on a consensus group." },
    { id: "S2", file: "studio-02-collab-editor.html", title: "Design a Collaborative Editor",           afterPart: 4, related: ["06", "15", "16"], blurb: "Real-time multi-user editing with offline support, merging and a server that may not be needed." },
    { id: "S3", file: "studio-03-multi-region-kv.html", title: "Design a Multi-Region Key-Value Store", afterPart: 5, related: ["05", "07", "18"], blurb: "Per-key consistency choices, replica placement, failover and the latency every choice costs." }
  ];

  var DIST_TOOLS = [
    { id: "maelstrom", name: "Maelstrom & Gossip Glomers", chapters: ["03", "08", "10", "15"], blurb: "Write nodes in any language and have a workbench simulate networks, faults and check correctness." },
    { id: "jepsen",    name: "Jepsen",                    chapters: ["05", "19"],             blurb: "A framework that runs real databases, injects partitions and checks the recorded histories." },
    { id: "porcupine", name: "Porcupine & Knossos",       chapters: ["05", "19"],             blurb: "Linearizability checkers that take a history of operations and look for a legal order." },
    { id: "tlaplus",   name: "TLA+ & the TLC model checker", chapters: ["20", "09", "13"],    blurb: "Write a design as a state machine and let the model checker explore every interleaving." },
    { id: "etcd",      name: "etcd & etcdctl",            chapters: ["10", "11", "04"],       blurb: "Run a real three-node Raft cluster, watch leader changes and take leases." },
    { id: "zookeeper", name: "ZooKeeper CLI",             chapters: ["11"],                   blurb: "Create ephemeral and sequential znodes and build an election recipe by hand." },
    { id: "toxiproxy", name: "Toxiproxy & tc netem",      chapters: ["03", "18", "19"],       blurb: "Add latency, loss and partitions between real processes to see protocols misbehave." },
    { id: "kafka",     name: "Kafka CLI tools",           chapters: ["17"],                   blurb: "Create partitioned topics, run consumer groups and inspect offsets and replicas." }
  ];


  /* ---------- Course 5: Reliability & Operations ---------- */

  var OPS_PARTS = [
    { title: "Orientation",                 blurb: "What changes when a system has real users, real traffic and a pager." },
    { title: "Defining Reliability",        blurb: "Availability arithmetic, SLIs, SLOs and error budgets: deciding how reliable is reliable enough." },
    { title: "Observability",               blurb: "Metrics, logs and traces: asking new questions of a running system without shipping new code." },
    { title: "Performance & Capacity",      blurb: "Queueing theory, tail latency, load testing and keeping a service upright when demand exceeds supply." },
    { title: "Changing Production Safely",  blurb: "Deploys, configuration, containers and orchestration, and limiting the blast radius of every change." },
    { title: "When Things Break",           blurb: "Incident response, learning from failure, disaster recovery and breaking things on purpose." },
    { title: "Sustaining Systems",          blurb: "Cost, efficiency and the human side of running software for years." }
  ];

  var OPS_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                           blurb: "From building systems to running them: what operations is, and how this course builds on the first four." },

    { id: "01", part: 1, depth: "deep",  file: "01-availability-math.html",   title: "What Reliability Means",               blurb: "Nines, serial and parallel composition, MTBF and MTTR, and why recovery speed often beats prevention." },
    { id: "02", part: 1, depth: "deep",  file: "02-slos-error-budgets.html",  title: "SLIs, SLOs & Error Budgets",           blurb: "Measuring what users feel, choosing targets, and spending an error budget on purpose." },
    { id: "03", part: 1, depth: "intro", file: "03-sre-toil.html",            title: "Toil, Automation & Ownership",         blurb: "The SRE model, toil budgets, and who carries the pager for what." },

    { id: "04", part: 2, depth: "deep",  file: "04-metrics.html",             title: "Metrics, Percentiles & Histograms",    blurb: "Counters, gauges and histograms, why percentiles cannot be averaged, RED and USE, and the cardinality trap." },
    { id: "05", part: 2, depth: "core",  file: "05-logs-events.html",         title: "Logs & Structured Events",             blurb: "From printf to wide structured events, log levels, sampling and the cost of keeping everything." },
    { id: "06", part: 2, depth: "deep",  file: "06-tracing.html",             title: "Distributed Tracing",                  blurb: "Spans, context propagation, sampling, critical paths and OpenTelemetry." },
    { id: "07", part: 2, depth: "core",  file: "07-alerting-oncall.html",     title: "Alerting & On-Call",                   blurb: "Symptom-based alerts, multi-window burn-rate alerting, runbooks and fighting alert fatigue." },

    { id: "08", part: 3, depth: "deep",  file: "08-queueing-theory.html",     title: "Queueing Theory for Engineers",        blurb: "Utilization, the latency knee, M/M/1 and M/M/c intuition, variability and why 80% busy is already busy." },
    { id: "09", part: 3, depth: "deep",  file: "09-tail-latency.html",        title: "Tail Latency at Scale",                blurb: "Fan-out amplification, hedged and tied requests, and designing for the 99.9th percentile." },
    { id: "10", part: 3, depth: "core",  file: "10-load-testing-capacity.html", title: "Load Testing & Capacity Planning",   blurb: "Open versus closed load, coordinated omission, headroom, forecasting and saturation tests." },
    { id: "11", part: 3, depth: "deep",  file: "11-overload.html",            title: "Overload, Load Shedding & Metastability", blurb: "Admission control, adaptive concurrency limits, retry budgets and failures that sustain themselves." },

    { id: "12", part: 4, depth: "deep",  file: "12-deployments.html",         title: "Deployment Strategies",                blurb: "Rolling, blue-green and canary releases, automated canary analysis and fast, boring rollbacks." },
    { id: "13", part: 4, depth: "core",  file: "13-config-iac.html",          title: "Configuration & Infrastructure as Code", blurb: "Config changes as the leading cause of outages, staged config rollout, GitOps and immutable infrastructure." },
    { id: "14", part: 4, depth: "core",  file: "14-orchestration.html",       title: "Containers & Orchestration",           blurb: "Kubernetes from first principles: desired state, controllers, pods, services, probes, requests and limits." },
    { id: "15", part: 4, depth: "deep",  file: "15-blast-radius.html",        title: "Blast Radius: Cells, Shuffle Sharding & Static Stability", blurb: "Containing failures by design: cells, shuffle sharding, control versus data planes and static stability." },

    { id: "16", part: 5, depth: "core",  file: "16-incident-response.html",   title: "Incident Response",                    blurb: "Detection, roles, mitigation before diagnosis, communication and knowing when it is over." },
    { id: "17", part: 5, depth: "core",  file: "17-postmortems.html",         title: "Postmortems & Learning from Incidents", blurb: "Blameless reviews, contributing factors instead of root causes, and turning incidents into change." },
    { id: "18", part: 5, depth: "core",  file: "18-disaster-recovery.html",   title: "Backups & Disaster Recovery",          blurb: "RPO and RTO, restore testing, region evacuation and the backups that only count if you can restore them." },
    { id: "19", part: 5, depth: "core",  file: "19-chaos-gamedays.html",      title: "Chaos Engineering & Game Days",        blurb: "Hypotheses, steady state, controlled experiments and rehearsing failure before it rehearses you." },

    { id: "20", part: 6, depth: "intro", file: "20-cost-efficiency.html",     title: "Cost & Efficiency",                    blurb: "Cloud cost models, utilization, right-sizing and treating efficiency as an engineering property." },
    { id: "21", part: 6, depth: "intro", file: "21-where-next.html",          title: "Where Next: On to Security",           blurb: "What you can now run and reason about, and why the next course assumes some users are adversaries." }
  ];

  var OPS_LABS = [
    { id: "L1", file: "lab-01-slo-burn.html",       title: "SLOs & Burn-Rate Alerts",          afterPart: 1, related: ["02", "07"],       blurb: "Compute SLIs and error budgets from request logs, then build multi-window burn-rate alerts and test them on synthetic incidents." },
    { id: "L2", file: "lab-02-metrics.html",        title: "A Metrics Library",                afterPart: 2, related: ["04", "net:13"],   blurb: "Counters and histograms with buckets, mergeable percentiles across hosts, and an exposition endpoint." },
    { id: "L3", file: "lab-03-tracing.html",        title: "Tracing from Scratch",             afterPart: 2, related: ["06", "arch:13"],  blurb: "Propagate trace context across simulated services, rebuild trace trees and find the critical path." },
    { id: "L4", file: "lab-04-queueing.html",       title: "Queues, Load Tests & Coordinated Omission", afterPart: 3, related: ["08", "10", "sys:14"], blurb: "A discrete-event simulator checked against queueing formulas, and a load generator that does not lie." },
    { id: "L5", file: "lab-05-load-shedding.html",  title: "Adaptive Concurrency & Load Shedding", afterPart: 3, related: ["11", "arch:17"], blurb: "Drive a simulated service into a metastable failure, then protect it with admission control and AIMD limits." },
    { id: "L6", file: "lab-06-canary.html",         title: "Automated Canary Analysis",        afterPart: 4, related: ["12", "04"],       blurb: "Compare canary and baseline metrics statistically and decide promote or roll back, without fooling yourself." }
  ];

  var OPS_CASES = [
    { id: "C1", file: "case-01-tail-at-scale.html",    title: "The Tail at Scale",                    pattern: "Tail-tolerant design",        related: ["09", "08"],       blurb: "Google's lessons on why rare slowness dominates large fan-out systems, and the techniques that tame it." },
    { id: "C2", file: "case-02-aws-2021.html",         title: "AWS us-east-1, December 2021",         pattern: "Hidden internal dependencies", related: ["15", "16"],      blurb: "Congestion on an internal network, monitoring that went dark, and slow recovery for many services." },
    { id: "C3", file: "case-03-slack-2021.html",       title: "Slack's January 2021 Outage",          pattern: "Scaling under a surge",       related: ["10", "11"],       blurb: "The first working day of the year, a saturated network layer and autoscaling that made things worse." },
    { id: "C4", file: "case-04-roblox-2021.html",      title: "Roblox: 73 Hours Down",                pattern: "Shared infrastructure failure", related: ["16", "17", "15"], blurb: "A coordination system under unusual load, a storage pathology and a long, careful recovery." },
    { id: "C5", file: "case-05-crowdstrike-2024.html", title: "CrowdStrike, July 2024",               pattern: "Unstaged content rollout",    related: ["13", "12"],       blurb: "A content update pushed to millions of machines at once, and why staged rollout matters for config too." },
    { id: "C6", file: "case-06-atlassian-2022.html",   title: "Atlassian: The Two-Week Restore",      pattern: "Recovery at the wrong granularity", related: ["18", "16"], blurb: "Sites deleted by a maintenance script, and backups that could not restore a few customers quickly." },
    { id: "C7", file: "case-07-kayenta.html",          title: "Netflix Kayenta: Canaries by Statistics", pattern: "Automated canary analysis", related: ["12", "04"],       blurb: "Comparing canary and baseline clusters metric by metric before a release goes everywhere." },
    { id: "C8", file: "case-08-static-stability.html", title: "Static Stability at AWS",              pattern: "Data plane survives control plane", related: ["15", "18"], blurb: "Designing systems that keep working when the systems that change them are down." }
  ];

  var OPS_STUDIOS = [
    { id: "S1", file: "studio-01-observability.html", title: "Design Observability for Checkout",   afterPart: 2, related: ["02", "04", "06", "07"], blurb: "SLIs, SLOs, dashboards, traces and alerts for a checkout flow that spans six services." },
    { id: "S2", file: "studio-02-flash-sale.html",    title: "Prepare for a Flash Sale",            afterPart: 3, related: ["08", "10", "11"], blurb: "Forecast, load-test, add headroom and plan degradation for a launch with twenty times normal traffic." },
    { id: "S3", file: "studio-03-incident.html",      title: "Run an Incident: A Tabletop Exercise", afterPart: 5, related: ["16", "17", "07"], blurb: "A staged outage you work through as incident commander, from first page to postmortem." }
  ];

  var OPS_TOOLS = [
    { id: "prometheus", name: "Prometheus & PromQL",      chapters: ["04", "07", "02"], blurb: "Scrape metrics, query rates and histograms, and write the alert rules you designed." },
    { id: "grafana",    name: "Grafana",                  chapters: ["04", "02"],       blurb: "Turn metrics into dashboards that answer one question each." },
    { id: "otel",       name: "OpenTelemetry & Jaeger",   chapters: ["06", "05"],       blurb: "Instrument a small service, propagate context and look at real traces." },
    { id: "loadgen",    name: "k6, wrk2 & vegeta",        chapters: ["10", "08", "09"], blurb: "Generate open-model load at a fixed rate and read latency histograms honestly." },
    { id: "kubectl",    name: "kind & kubectl",           chapters: ["14", "12"],       blurb: "Run Kubernetes on your laptop, roll out a deployment, break a probe and watch reconciliation." },
    { id: "stress",     name: "stress-ng & tc netem",     chapters: ["11", "19"],       blurb: "Starve a machine of CPU, memory or network and observe how your service degrades.", linux: true },
    { id: "chaos",      name: "Chaos tools",              chapters: ["19"],             blurb: "Chaos Mesh, Toxiproxy and friends: controlled fault injection with a blast radius you choose." },
    { id: "runbook",    name: "Runbooks & incident templates", chapters: ["16", "17", "07"], blurb: "Plain-text templates for runbooks, incident channels and postmortems you can copy." }
  ];


  /* ---------- Course 6: System Design Studio (capstone) ---------- */

  var DESIGN_PARTS = [
    { title: "Orientation",                 blurb: "What a design problem really asks, and how this capstone uses everything before it." },
    { title: "The Method",                  blurb: "A repeatable framework, napkin maths, the building blocks, and how to communicate trade-offs." },
    { title: "Foundational Designs",        blurb: "Small, reusable systems that appear inside every larger design." },
    { title: "Social & Real-Time",          blurb: "Feeds, messaging, search and trending: read-heavy systems with hot spots and fan-out." },
    { title: "Media, Geo & Marketplaces",   blurb: "Big files, moving things on a map, and contended inventory." },
    { title: "Money & Infrastructure",      blurb: "Correctness-critical and platform systems: payments, schedulers, crawlers and telemetry." },
    { title: "Beyond",                      blurb: "Designing around machine learning, and growing into a senior engineer." }
  ];

  var DESIGN_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                         blurb: "How design problems differ from coding problems, and how to use the worked designs and studios." },

    { id: "01", part: 1, depth: "deep",  file: "01-framework.html",           title: "A Framework for Design Problems",    blurb: "Requirements, estimates, interfaces, data, architecture, deep dives and trade-offs, in that order and why." },
    { id: "02", part: 1, depth: "deep",  file: "02-estimation.html",          title: "Back-of-the-Envelope Estimation",    blurb: "Numbers to remember, QPS, storage, bandwidth and machine counts, and sanity checks that catch mistakes." },
    { id: "03", part: 1, depth: "core",  file: "03-building-blocks.html",     title: "The Building Blocks, Revisited",     blurb: "Load balancers, caches, CDNs, queues, databases, object stores and search: what each buys and costs." },
    { id: "04", part: 1, depth: "core",  file: "04-tradeoffs-communication.html", title: "Trade-offs, Communication & Design Docs", blurb: "Thinking aloud, driving the discussion, writing a design doc, and what senior signals look like." },

    { id: "05", part: 2, depth: "deep",  file: "05-rate-limiter.html",        title: "Design a Rate Limiter",              blurb: "Token buckets and sliding windows, local versus global limits, and failing open or closed." },
    { id: "06", part: 2, depth: "deep",  file: "06-distributed-cache.html",   title: "Design a Distributed Cache",         blurb: "Partitioning, replication, eviction, hot keys and the consistency of cached data." },
    { id: "07", part: 2, depth: "core",  file: "07-unique-ids.html",          title: "Design Unique ID Generation",        blurb: "UUIDs, ticket servers, Snowflake-style IDs, ordering and clock problems." },
    { id: "08", part: 2, depth: "deep",  file: "08-object-storage.html",      title: "Design Object Storage",              blurb: "Metadata versus data, erasure coding, durability arithmetic and multipart uploads." },

    { id: "09", part: 3, depth: "deep",  file: "09-news-feed.html",           title: "Design a News Feed",                 blurb: "Fan-out on write versus read, celebrities, ranking and caching timelines." },
    { id: "10", part: 3, depth: "deep",  file: "10-chat-presence.html",       title: "Design Chat & Presence",             blurb: "Persistent connections, message ordering, delivery receipts, group fan-out and who is online." },
    { id: "11", part: 3, depth: "core",  file: "11-search-typeahead.html",    title: "Design Search & Typeahead",          blurb: "Inverted indexes at scale, tries and prefix caches, ranking and freshness." },
    { id: "12", part: 3, depth: "core",  file: "12-top-k-trending.html",      title: "Design Top-K & Trending",            blurb: "Heavy hitters over streams, count-min sketches, windows and approximate answers." },

    { id: "13", part: 4, depth: "deep",  file: "13-video-streaming.html",     title: "Design Video Streaming",             blurb: "Upload, transcoding pipelines, adaptive bitrate, CDNs and the economics of bytes." },
    { id: "14", part: 4, depth: "deep",  file: "14-ride-matching.html",       title: "Design Ride Matching",               blurb: "Location updates, geospatial indexes, matching and the dispatch state machine." },
    { id: "15", part: 4, depth: "core",  file: "15-ticketing.html",           title: "Design Ticketing & Flash Sales",     blurb: "Seat holds with expiry, contention on hot inventory, queues and fairness." },

    { id: "16", part: 5, depth: "deep",  file: "16-payments.html",            title: "Design a Payment System",            blurb: "Idempotency, double-entry ledgers, payment service providers, reconciliation and exactly-once money." },
    { id: "17", part: 5, depth: "core",  file: "17-job-scheduler.html",       title: "Design a Distributed Job Scheduler", blurb: "Delayed and recurring jobs, leases, retries, priorities and at-least-once execution." },
    { id: "18", part: 5, depth: "core",  file: "18-web-crawler.html",         title: "Design a Web Crawler",               blurb: "The frontier, politeness, deduplication, traps and crawling a billion pages." },
    { id: "19", part: 5, depth: "core",  file: "19-telemetry-platform.html",  title: "Design a Metrics & Logging Platform", blurb: "High-volume ingestion, time-series storage, downsampling, cardinality and queries." },

    { id: "20", part: 6, depth: "core",  file: "20-ml-systems.html",          title: "Designing with ML & LLMs",           blurb: "Model serving, feature stores, embeddings and vector search, retrieval-augmented generation and their failure modes." },
    { id: "21", part: 6, depth: "intro", file: "21-where-next.html",          title: "Where Next: Growing as a Senior Engineer", blurb: "Judgment, influence and continued learning, and how to keep this whole path fresh." }
  ];

  var DESIGN_LABS = [
    { id: "L1", file: "lab-01-estimation.html",    title: "Estimation Drills",                 afterPart: 1, related: ["02"],             blurb: "A napkin-maths toolkit and a checked set of estimation problems, from QPS to disk counts." },
    { id: "L2", file: "lab-02-rate-limiters.html", title: "Rate Limiters",                     afterPart: 2, related: ["05", "arch:17"],  blurb: "Token bucket, sliding-window log and counter, then a global limiter over a shared store with clock skew." },
    { id: "L3", file: "lab-03-feed-fanout.html",   title: "Feed Fan-out Simulator",            afterPart: 3, related: ["09"],             blurb: "Compare push, pull and hybrid timelines on a power-law follower graph, measuring work and latency." },
    { id: "L4", file: "lab-04-sketches.html",      title: "Sketches: Count-Min, HyperLogLog & Top-K", afterPart: 3, related: ["12", "19"], blurb: "Approximate counting with error bounds you can test, and a streaming top-K." },
    { id: "L5", file: "lab-05-geo-index.html",     title: "A Geospatial Index",                afterPart: 4, related: ["14"],             blurb: "Geohashes and a quadtree for nearest-driver queries, benchmarked against brute force." },
    { id: "L6", file: "lab-06-job-scheduler.html", title: "A Durable Job Scheduler",           afterPart: 5, related: ["17", "dist:04"],  blurb: "Delayed jobs, leases, retries with backoff and idempotent handlers, tested with crashes." }
  ];

  var DESIGN_CASES = [
    { id: "C1", file: "case-01-twitter-timelines.html", title: "Twitter's Timelines at Scale",       pattern: "Fan-out on write",           related: ["09", "06"],       blurb: "Precomputed home timelines in memory, and the special handling that very large accounts need." },
    { id: "C2", file: "case-02-instagram-ids.html",    title: "Sharding & IDs at Instagram",         pattern: "Time-ordered IDs in the database", related: ["07", "data:16"], blurb: "Generating sortable 64-bit IDs inside PostgreSQL shards without a central service." },
    { id: "C3", file: "case-03-whatsapp.html",         title: "WhatsApp: Millions of Connections per Server", pattern: "Lightweight processes", related: ["10", "sys:18"], blurb: "Erlang, FreeBSD tuning and a tiny team serving a huge messaging network." },
    { id: "C4", file: "case-04-uber-h3.html",          title: "Uber's H3 Hexagonal Grid",            pattern: "Geospatial indexing",         related: ["14"],             blurb: "Why hexagons, how hierarchical cells work, and what a grid buys a marketplace." },
    { id: "C5", file: "case-05-netflix-open-connect.html", title: "Netflix Open Connect",             pattern: "Own the edge",                related: ["13", "net:13"],   blurb: "Netflix's own CDN appliances inside ISPs, filled off-peak and steered per request." },
    { id: "C6", file: "case-06-stripe-idempotency.html", title: "Idempotency Keys at Stripe",         pattern: "Safe retries for money",      related: ["16", "arch:09"],  blurb: "Making payment APIs safe to retry, and the state machine behind each key." },
    { id: "C7", file: "case-07-slack-realtime.html",   title: "Slack's Real-Time Messaging",         pattern: "Channel servers & gateways",  related: ["10"],             blurb: "Consistent-hashed channel servers, gateway servers near users and fan-out of every message." },
    { id: "C8", file: "case-08-dropbox-magic-pocket.html", title: "Dropbox Magic Pocket",            pattern: "Exabyte object storage",      related: ["08", "data:13"],  blurb: "Leaving the public cloud for an in-house block store with erasure coding and verification everywhere." }
  ];

  var DESIGN_STUDIOS = [
    { id: "S1", file: "studio-01-file-sync.html",      title: "Design File Sync (Dropbox)",          afterPart: 2, related: ["08", "dist:15"],  blurb: "Chunking, deduplication, metadata, sync conflicts and clients that go offline for weeks." },
    { id: "S2", file: "studio-02-photo-sharing.html",  title: "Design Photo Sharing (Instagram)",    afterPart: 3, related: ["09", "08", "13"], blurb: "Uploads, a feed, likes and comments, a CDN and the hot accounts that break naive designs." },
    { id: "S3", file: "studio-03-code-judge.html",     title: "Design an Online Code Judge",         afterPart: 5, related: ["17", "sys:19"],   blurb: "Untrusted code in sandboxes, a submission queue, contest spikes and fair results." },
    { id: "S4", file: "studio-04-booking.html",        title: "Design a Hotel Booking System",       afterPart: 4, related: ["15", "data:11"],  blurb: "Inventory by night, no double bookings, holds, overbooking policy and search that scales." },
    { id: "S5", file: "studio-05-exchange.html",       title: "Design a Stock Exchange",             afterPart: 5, related: ["16", "arch:16"],  blurb: "A matching engine, a sequenced input log, market data fan-out and microseconds that matter." },
    { id: "S6", file: "studio-06-message-queue.html",  title: "Design a Distributed Message Queue",  afterPart: 5, related: ["dist:17", "dist:10"], blurb: "Partitions, replication, consumer groups, retention and delivery guarantees, built from scratch." },
    { id: "S7", file: "studio-07-ad-clicks.html",      title: "Design an Ad Click Aggregator",       afterPart: 5, related: ["12", "dist:17"],  blurb: "Billions of events, windowed counts, exactly-once billing and reconciliation." },
    { id: "S8", file: "studio-08-live-streaming.html", title: "Design Live Streaming with Chat",     afterPart: 6, related: ["13", "10"],       blurb: "Ingest, low-latency delivery, a chat room of a million viewers and a broadcast that cannot buffer." }
  ];

  var DESIGN_TOOLS = [
    { id: "excalidraw", name: "Excalidraw & whiteboards", chapters: ["01", "04"],     blurb: "Sketch boxes and arrows fast, the way you will in a design review or interview." },
    { id: "napkin",     name: "Napkin-maths reference",   chapters: ["02", "08"],     blurb: "Latency and throughput numbers worth memorising, and how to derive the rest." },
    { id: "design-doc", name: "Design-doc templates",     chapters: ["04", "01"],     blurb: "A one-page and a full design-doc template, with a review checklist." },
    { id: "mock",       name: "Mock interview kit",       chapters: ["01", "04", "21"], blurb: "Timers, prompts and a scoring rubric for practising with a friend." },
    { id: "redis-lab",  name: "Redis for prototyping",    chapters: ["05", "06", "12"], blurb: "Try rate limiters, caches and sorted-set leaderboards on a real data structure server." }
  ];


  /* ---------- Course 6: Security Engineering (added after the gap analysis) ---------- */

  var SEC_PARTS = [
    { title: "Orientation",                 blurb: "Thinking like an attacker, and why security is a property of the whole system." },
    { title: "Foundations",                 blurb: "Threat models, design principles, the cryptography you actually use, and managing keys and secrets." },
    { title: "Identity & Access",           blurb: "Proving who someone is, keeping them signed in, delegating access and deciding what they may do." },
    { title: "Application Security",        blurb: "The bug classes behind most breaches: injection, the browser's security model, server-side request forgery and the supply chain." },
    { title: "Infrastructure Security",     blurb: "Networks without a trusted inside, cloud identities, tenant isolation and abuse at scale." },
    { title: "Data & Operations",           blurb: "Protecting data and privacy, detecting attacks, and building security into design reviews." }
  ];

  var SEC_CHAPTERS = [
    { id: "00", part: 0, depth: "intro", file: "00-start-here.html",          title: "Start Here",                          blurb: "Attackers, assets and trust: how security fits into everything the earlier courses built." },

    { id: "01", part: 1, depth: "deep",  file: "01-threat-modeling.html",     title: "Threat Modeling",                     blurb: "Assets, adversaries, trust boundaries, STRIDE and attack trees: finding the weak points before an attacker does." },
    { id: "02", part: 1, depth: "core",  file: "02-principles.html",          title: "Security Design Principles",          blurb: "Least privilege, defence in depth, fail-safe defaults, complete mediation and a small trusted computing base." },
    { id: "03", part: 1, depth: "deep",  file: "03-applied-crypto.html",      title: "Applied Cryptography",                blurb: "Hashes, MACs, authenticated encryption, public keys, signatures and randomness, and the mistakes that break them." },
    { id: "04", part: 1, depth: "deep",  file: "04-keys-secrets-pki.html",    title: "Keys, Secrets & PKI",                 blurb: "Key management, envelope encryption, rotation, secret stores, certificate authorities and mutual TLS." },

    { id: "05", part: 2, depth: "deep",  file: "05-authentication.html",      title: "Authentication",                      blurb: "Password storage, multi-factor authentication, passkeys and credential stuffing." },
    { id: "06", part: 2, depth: "core",  file: "06-sessions-tokens.html",     title: "Sessions, Cookies & Tokens",          blurb: "Server sessions versus signed tokens, JWT pitfalls, cookie flags, refresh tokens and revocation." },
    { id: "07", part: 2, depth: "deep",  file: "07-oauth-oidc.html",          title: "OAuth 2.0 & OpenID Connect",          blurb: "Delegated access, the authorization-code flow with PKCE, scopes, ID tokens and single sign-on." },
    { id: "08", part: 2, depth: "deep",  file: "08-authorization.html",       title: "Authorization",                       blurb: "RBAC, ABAC and relationship-based access, policy engines, the confused deputy and broken object-level authorization." },

    { id: "09", part: 3, depth: "deep",  file: "09-injection.html",           title: "Injection & Untrusted Input",         blurb: "SQL and command injection, path traversal and unsafe deserialization, and why parameterization beats filtering." },
    { id: "10", part: 3, depth: "deep",  file: "10-web-security.html",        title: "The Browser Security Model",          blurb: "Same-origin policy, XSS, CSRF, CORS, content security policy and cookie attributes." },
    { id: "11", part: 3, depth: "core",  file: "11-ssrf-server-side.html",    title: "SSRF & Server-Side Risks",            blurb: "Making your server fetch what the attacker wants, cloud metadata endpoints and other server-side traps." },
    { id: "12", part: 3, depth: "core",  file: "12-memory-supply-chain.html", title: "Memory Safety & the Supply Chain",    blurb: "Buffer overflows in one picture, memory-safe languages, dependencies, signed builds and SBOMs." },

    { id: "13", part: 4, depth: "core",  file: "13-zero-trust.html",          title: "Network Security & Zero Trust",       blurb: "Segmentation, firewalls and why the trusted internal network is a myth: identity-aware access everywhere." },
    { id: "14", part: 4, depth: "core",  file: "14-cloud-container.html",     title: "Cloud & Container Security",          blurb: "Cloud IAM, least-privilege roles, metadata services, container isolation and secrets in orchestrators." },
    { id: "15", part: 4, depth: "deep",  file: "15-multi-tenancy.html",       title: "Multi-Tenancy & Isolation",           blurb: "Silo, pool and bridge models, tenant-aware data access, noisy neighbours and per-tenant keys." },
    { id: "16", part: 4, depth: "core",  file: "16-abuse-dos.html",           title: "Abuse, Bots & Denial of Service",     blurb: "Credential stuffing, scraping, fraud signals, DDoS mitigation and designing for adversarial load." },

    { id: "17", part: 5, depth: "deep",  file: "17-data-protection.html",     title: "Data Protection & Privacy",           blurb: "Encryption at rest and in transit, tokenization, minimization, deletion across logs and backups, and residency." },
    { id: "18", part: 5, depth: "core",  file: "18-detection-response.html",  title: "Detection & Security Incidents",      blurb: "Audit logs, detection engineering, security incident response and what to keep for forensics." },
    { id: "19", part: 5, depth: "core",  file: "19-secure-design-review.html", title: "Secure Design Reviews",              blurb: "Security sections in design docs, a review checklist, secure defaults and a security-minded engineering culture." },
    { id: "20", part: 5, depth: "intro", file: "20-where-next.html",          title: "Where Next: On to System Design",     blurb: "What you can now defend, a reading list, and carrying a security lens into every design." }
  ];

  var SEC_LABS = [
    { id: "L1", file: "lab-01-passwords-macs.html", title: "Passwords, MACs & Timing",         afterPart: 1, related: ["03", "05"],        blurb: "Store passwords with a slow salted hash, upgrade hashes on login, sign messages with HMAC and stop replays." },
    { id: "L2", file: "lab-02-tokens.html",        title: "Build and Break a Token Format",    afterPart: 2, related: ["06", "03"],        blurb: "A JWT-like signed token, then the attacks: algorithm confusion, missing checks, expiry and revocation." },
    { id: "L3", file: "lab-03-oauth-pkce.html",    title: "OAuth with PKCE, Simulated",        afterPart: 2, related: ["07"],              blurb: "An in-process authorization server, client and API, with redirect, state and PKCE checks you can attack." },
    { id: "L4", file: "lab-04-authz-engine.html",  title: "A Relationship-Based Authorization Engine", afterPart: 2, related: ["08", "15"],  blurb: "From roles to Zanzibar-style relation tuples, with tests that catch insecure direct object references." },
    { id: "L5", file: "lab-05-injection.html",     title: "Find and Fix Injection",            afterPart: 3, related: ["09", "11"],        blurb: "Exploit a vulnerable app's SQL, path and URL-fetch handling, then fix each bug for good." },
    { id: "L6", file: "lab-06-envelope-encryption.html", title: "Envelope Encryption & Crypto-Shredding", afterPart: 5, related: ["04", "17", "15"], blurb: "Per-tenant data keys wrapped by a master key, key rotation, and deleting a tenant by destroying its key." }
  ];

  var SEC_CASES = [
    { id: "C1", file: "case-01-heartbleed.html",    title: "Heartbleed",                          pattern: "Memory safety",              related: ["12", "03"],       blurb: "A missing bounds check in OpenSSL that leaked server memory, including private keys, to anyone who asked." },
    { id: "C2", file: "case-02-equifax.html",       title: "Equifax, 2017",                       pattern: "Patch and inventory",        related: ["12", "18"],       blurb: "An unpatched web framework, an expired certificate on a monitoring device and months of undetected access." },
    { id: "C3", file: "case-03-capital-one.html",   title: "Capital One, 2019",                   pattern: "SSRF to cloud credentials",  related: ["11", "14"],       blurb: "A misconfigured firewall, a metadata endpoint and an over-privileged role." },
    { id: "C4", file: "case-04-log4shell.html",     title: "Log4Shell",                           pattern: "Injection through a feature", related: ["09", "12"],      blurb: "A logging library that looked up and loaded code named inside log messages." },
    { id: "C5", file: "case-05-storm-0558.html",    title: "Storm-0558 and a Stolen Signing Key", pattern: "Key management",             related: ["04", "06"],       blurb: "A consumer signing key that could mint enterprise tokens, and what an independent review concluded." },
    { id: "C6", file: "case-06-xz-backdoor.html",   title: "The xz Backdoor",                     pattern: "Open-source supply chain",   related: ["12", "19"],       blurb: "Years of patient social engineering, a hidden build-time payload and a half-second delay that gave it away." },
    { id: "C7", file: "case-07-beyondcorp.html",    title: "BeyondCorp: Google's Zero Trust",     pattern: "No trusted network",         related: ["13", "05"],       blurb: "Moving access decisions from the network perimeter to devices and users." },
    { id: "C8", file: "case-08-zanzibar.html",      title: "Zanzibar: Authorization at Google Scale", pattern: "Relationship-based access", related: ["08", "dist:07"], blurb: "One global system answering permission checks for many products, with consistency tokens against stale ACLs." }
  ];

  var SEC_STUDIOS = [
    { id: "S1", file: "studio-01-saas-identity.html", title: "Design Identity & Access for a Multi-Tenant SaaS", afterPart: 4, related: ["07", "08", "15"], blurb: "Single sign-on, roles and sharing, tenant isolation, admin impersonation and audit." },
    { id: "S2", file: "studio-02-threat-model.html",  title: "Threat-Model a File-Sharing Service",  afterPart: 3, related: ["01", "09", "11"], blurb: "Uploads, previews, share links and an API: find the threats, rank them and design the mitigations." },
    { id: "S3", file: "studio-03-secrets-manager.html", title: "Design a Secrets Manager",          afterPart: 5, related: ["04", "13", "18"], blurb: "Storing, leasing and rotating secrets for thousands of services, and surviving the loss of the master key holder." }
  ];

  var SEC_TOOLS = [
    { id: "zap",      name: "OWASP ZAP",                 chapters: ["09", "10", "11"],  blurb: "An intercepting proxy and scanner for testing your own web apps." },
    { id: "semgrep",  name: "Semgrep & static analysis", chapters: ["09", "19"],        blurb: "Search code for insecure patterns with rules you can read and write." },
    { id: "deps",     name: "Dependency & image scanners", chapters: ["12", "14"],      blurb: "pip-audit, OSV-Scanner and Trivy: find known-vulnerable packages before attackers do." },
    { id: "secrets-scan", name: "Secret scanners",       chapters: ["04", "12"],        blurb: "gitleaks and friends: catch keys committed to a repository." },
    { id: "nmap",     name: "nmap",                      chapters: ["13", "14"],        blurb: "See which ports and services your own machines actually expose." },
    { id: "jwt-tools", name: "Token and certificate inspection", chapters: ["06", "07", "04"], blurb: "Decode JWTs, inspect certificates and test TLS settings from the command line." }
  ];


  window.CS_DEPTH_LABEL = { deep: "Deep dive", core: "Core", intro: "Quick intro" };

  /* status: "done" | "building" | "planned". Planned courses appear on the hub only. */
  window.CS_COURSES = [
    { id: "net", dir: "networking", mark: "NZ", title: "Networking from Zero", subtitle: "to distributed systems",
      tagline: "From bits on a wire to replication and consensus: how computers talk, and how many of them act as one.",
      status: "done", parts: NET_PARTS, chapters: NET_CHAPTERS, labs: NET_LABS, cases: NET_CASES, studios: [], tools: NET_TOOLS,
      roadmapBlurbs: { labs: "Build the ideas yourself in Python, from a chat server to a toy Raft. Each lab says which part to finish first.",
                       cases: "Real systems and real outages, each built around one networking or distributed-systems pattern." } },
    { id: "sys", dir: "systems", mark: "HR", title: "How Programs Run", subtitle: "from the CPU to concurrency",
      tagline: "What happens inside one machine: processes, memory, files, durability, threads, locks and event loops.",
      status: "done", parts: SYS_PARTS, chapters: SYS_CHAPTERS, labs: SYS_LABS, cases: SYS_CASES, studios: SYS_STUDIOS, tools: SYS_TOOLS },
    { id: "data", dir: "data", mark: "DS", title: "Data Systems", subtitle: "how databases really work",
      tagline: "Storage engines, indexes, transactions and isolation, caching, replication, sharding and change data capture.",
      status: "done", parts: DATA_PARTS, chapters: DATA_CHAPTERS, labs: DATA_LABS, cases: DATA_CASES, studios: DATA_STUDIOS, tools: DATA_TOOLS },
    { id: "arch", dir: "architecture", mark: "SA", title: "Software Architecture & Design", subtitle: "structure that survives change",
      tagline: "Complexity and coupling, hexagonal design, APIs, monoliths and microservices, events, sagas, resilience and evolution.",
      status: "done", parts: ARCH_PARTS, chapters: ARCH_CHAPTERS, labs: ARCH_LABS, cases: ARCH_CASES, studios: ARCH_STUDIOS, tools: ARCH_TOOLS },
    { id: "dist", dir: "distributed", mark: "DD", title: "Distributed Systems, Deep", subtitle: "agreement under failure",
      tagline: "Leases and fencing, consistency models, Paxos and Raft in depth, distributed transactions, CRDTs and testing.",
      status: "done", parts: DIST_PARTS, chapters: DIST_CHAPTERS, labs: DIST_LABS, cases: DIST_CASES, studios: DIST_STUDIOS, tools: DIST_TOOLS },
    { id: "ops", dir: "reliability", mark: "RO", title: "Reliability & Operations", subtitle: "running systems for real",
      tagline: "SLOs and error budgets, observability, queueing and capacity, safe deploys and incident response.",
      status: "done", parts: OPS_PARTS, chapters: OPS_CHAPTERS, labs: OPS_LABS, cases: OPS_CASES, studios: OPS_STUDIOS, tools: OPS_TOOLS },
    { id: "sec", dir: "security", mark: "SE", title: "Security Engineering", subtitle: "systems that survive attackers",
      tagline: "Threat modeling, applied cryptography, authentication and OAuth, authorization, web and supply-chain security, zero trust, multi-tenancy and privacy.",
      status: "done", parts: SEC_PARTS, chapters: SEC_CHAPTERS, labs: SEC_LABS, cases: SEC_CASES, studios: SEC_STUDIOS, tools: SEC_TOOLS },
    { id: "design", dir: "design", mark: "SD", title: "System Design Studio", subtitle: "putting it all together",
      tagline: "A design framework and a dozen worked designs, from rate limiters to payment ledgers, and how to talk trade-offs.",
      status: "done", parts: DESIGN_PARTS, chapters: DESIGN_CHAPTERS, labs: DESIGN_LABS, cases: DESIGN_CASES, studios: DESIGN_STUDIOS, tools: DESIGN_TOOLS }
  ];
})();
