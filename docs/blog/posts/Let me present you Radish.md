---
date: 2026-03-09
categories:
  - Reinventing the Wheel
  - Tech Deep Dive
---

# I created an in-memory key-value DB, let me present you Radish! 

Hello! This is my first **"real"** article. Today's topic is about building your own in-memory key-value DB. 
The reason behind this choice is simple:

**I wanted to understand better what an in-memory db is**.

I always heard good words spent on Redis (and its creator) so I thought: What's the best way of learning a tool? — Creating something similar!
Follow the article to see how it went! (Spoiler: surprisingly good)
<!-- more -->

# What Radish is? (more broadly what is a key-value DB)
As I said Radish is an experimental project, we can also say a didactical project, aimed to re implement a key-value in-memory DB. 
So if you already know Redis/Valkey you may have familiarity with this concept, otherwise you can think about them as shared data-structures, accessible to clients around the web.
You can also imagine it as a giant python dictionary accessible on the web that supports several data-structures as values.

The concept evolved significantly from these definitions, but if we refer to the core idea, I still think this is the best definition out there.
An in-memory key-value DB is useful when you have data to share from producers to consumers (among others) that is not "easily" shared using a standard SQL DB table, for instance lists.

Going through all the Radish implementation is a long and exhausting exercise that you can do, if you are curious, by reading the documentation.
In this blog article I just want to summarize a few concepts that I loved while implementing Radish, hopefully you will love them too, or at least find it a good read.

***P.S. Radish is implemented in Julia — don't ask me why, I just picked up a language!***


# 1 - Radish at its core
Since we are developing a dictionary-like tool, let's start from the core. The Radish Core is based on two data structures: **RadishContext** and **Radishelement**.

The RadishContext is a Dict of `(string, RadishElement)` type.
```julia
RadishContext = Dict{String, RadishElement}
```

Every value is wrapped in a RadishElement that carries metadata:

```julia
mutable struct RadishElement
    value::Any # The real value (or datastructure)
    ttl::Union{Int, Nothing} # Time to live to manage expires
    tinit::DateTime # Init time to manage expires
    datatype::Symbol # Datatype symbol to efficiently look up the type
end
```
The core most important decision is to build Radish using a delegation pattern.
Commands that operate on the whole RadishContext or generic operations are called  **Hypercommands**. These commands handle the common logic (for instance: locking, TTL checking, key lookup).

The specific work is delegated to a smaller, RadishElement type specific command. They are called **Typecommands**. In the end **Hypercommands** and **Typecommands** are linked between using a **Typepalette** that defines the relationship.
```julia
S_PALETTE = Dict{String, Tuple}( #PALETTE type for strings
    "S_GET" => (sget, rget_or_expire!),
    # S_GET palette. It is linking the hypercommand `rget_or_expire!` to its type command `sget`
    "S_SET" => (sadd, radd!),
    "S_INCR" => (sincr!, rmodify!),
    # ... more string commands
)
```
This is the single most important design decision in Radish: it makes the system extensible, testable, and easy to reason about.

Adding a new type is easy because you rely on already defined **Hypercommands**, you just have to implement specific data type functions — in other words, Hypercommands provide a standardized way to access the RadishContext.

There are a lot of **Hypercommands** that support a lot of interfaces: get, add, modify, delete, get and modify, etc.

### S_GET example
To explain further this idea, let's take a look at the command `S_GET` the most simple command you can operate on `strings`, defined in the string palette above.

Whenever the client calls for an `S_GET` command, using lookup we know it must be routed to: `(sget, rget_or_expire!)`.

This means we are calling `rget_or_expire!` on the whole RadishContext which delegates the real get operation to the `sget` function.


# 2 - Sharded locks - how to handle concurrency
First of all, Radish is multi-threaded. This means that multiple clients are served concurrently, which requires explicit synchronization.
This was a deliberate choice of mine. On top of that, I think that understanding concurrency primitives is essential for systems engineering, and Radish is a good playground to explore them.

When multiple clients access shared state concurrently, bad things can happen:

```
Client A: reads counter = 10
Client B: reads counter = 10
Client A: writes counter = 11
Client B: writes counter = 11    ← Should be 12!
```

This is a **race condition** — the classic lost-update problem. A good system needs to prevent this!

The first idea is to hide every variable (RadishElement) behind a lock. Every time you need to read it, the system acquires the lock on that element. This prevents every other process from reading or writing. As you may feel, this is a good idea because the system will be safe, but it will make it very slow.

When every object has its own lock, the management becomes very expensive. Every lock has to be locked/unlocked (what if I have 1M objects?). On the other hand, some operations do not really require a lock, for instance reads.

To solve this I decided to use a **Sharded-Writeonly-Lock** implementation. It works as follows:

- Each key object is hashed into a smaller space. I used a space of dimension 256 - each piece is called **shard**.

- Every time you want to perform a write operation (**Hypercommands**: rmodify, rdelete, ...) the system acquires the lock on the whole shard. 

- It does the modification, and eventually it releases the lock.

When multiple processes are reading a variable, the lock is not needed — everyone can access it, because the value does not change. The problem is when you are reading while another process is modifying the variable, that is why on write the system locks and releases just after the modification is successful.


Pros: 

- Limited amount of locks to manage.

- Lock free reads. 

Cons:

- Locking N/256 keys together.

Of course this is not (possibly) the best design choice — it heavily depends on how read-intensive or write-intensive your usage is, and many other complex factors. I just want to remark that this is not a simple problem and that's why I loved it. I can only imagine the number of decisions like this that go into building complex systems.

# 3 - Time To Live, deleting expired keys

This is a common problem when you have an expire policy. You have some keys that are valid up to a certain time, then those are no longer available and you have to delete them.
The naive way is to loop on all the keys every *t* milliseconds and check every element. This may be a bad idea computationally speaking, so there are two very pragmatic strategies to handle this. 

1) **Deletion on lookup a.k.a lazy deletion**

Very simple, the system doesn't do anything. When an operation on the key is performed, the first check is validity. If the key is no longer valid, just delete it and act as if the key is not present in the DB.

Although this is a very valid idea, you may have situations in which a key with a TTL is created and never accessed. It will never be deleted if you use this method only.

2) **Random deletion a.k.a active deletion**

Another cool method is to have a random process that randomly subsamples keys and performs the active check. If an expired key is found, it deletes it. This process needs to be tuned, otherwise the risk is to have a lot of locks and computation power invested in keeping the DB clean instead of serving clients.

Radish combines the two deletion strategies with a smarter implementation for the active part that runs every `t` seconds. In particular, the workflow is the following:

- It samples 10% of the keys randomly

- It orders the keys into shards

- It performs a per-shard locking — it locks one shard at a time, checks only the sampled keys in that shard, and moves on.

This minimizes the time any single shard is locked, theoretically increasing the responsiveness of the system.


# 4 - Persistence - last topic for this blog post

When talking about in-memory DBs, we must talk about persistence. Unlike standard DBs, all the data is saved on RAM — this is exceptional from a performance point of view, but what about keeping the data safe or handling system restarts?

A good way to implement persistence is through periodic dumps. Unlike Redis, which uses the fork mechanism of the Unix system, I decided to implement an external process that takes care of it (the syncer process).

The dump is stored as a newline-delimited JSON file, this is an example of it:
``` json
{"key": "user:1", "value": "Alice", "ttl": 3600, "datatype": "string"}
{"key": "user:2", "value": "Bob", "ttl": null, "datatype": "string"}
```

The problem with full dumps is that you need to write all the data every time, which is very heavy — that is why I introduced a **Dirty Tracker mechanism**.

``` julia
mutable struct DirtyTracker
    modified::Set{String}    # Keys that were added/modified
    deleted::Set{String}     # Keys that were deleted
    lock::ReentrantLock      # Thread safety
end
```

Every **Hypercommand** that modifies state calls `mark_dirty!(tracker, key)` or `mark_deleted!(tracker, key)`.
In this way the internal system knows the modified or deleted keys. This system is efficient since at the end of the day it is just a **set insertion**.

Then, I partitioned the save space into shards — no full dump needed, we can split the save files exactly like the locks. It's like having a well-partitioned dataset where each shard maps to its own file.
The **Dirty Tracking** guides the syncer process to the shards that have to be rewritten because they contain *dirty* data.
This process runs every `t` seconds, configurable under the `config.yaml` file.

Great, we have now a method to create snapshots so we can keep the data safe. But what if the system crashes `x` milliseconds after a run of the syncer process?

Data written in that small amount of time will be lost forever!

A way to solve this using an **append only** log file (AOF).
The method is simple but reliable: every command is written into the AOF. When a dump is successful, the AOF is truncated.

Each line records the full command:

```
S_SET user:1 Alice 3600
S_INCR counter
L_PREPEND queue job42
```

If the system crashes we have a method to recover lost data: 

- Load the snapshot

- Load AOF

- Execute every command present in the AOF

This pattern of doing snapshots + AOF is a well-established method, also used by Redis.



# 5 - Bonus: Try it out

I have included two files: *docker* and *make*. These two helpers really bring Radish to life. If you are like me and you like to test projects hands-on, you may love them.

Here a small guide on how to do the same. 

```
1- Use the `git clone` command you to clone the repository.
2- Use the `make build` command to build the docker container of the full project.
3- Use the `make server` or `make server-logs` command to spawn a server instance, with logs or no logs visibility.
4- Use the `make client` command to spawn a client instance in CLI mode. So you can start sending commands.

```
There are also other utilities to simulate workloads:

```
- `make simload`	Run simulator in load-only mode, ingesting random data in the system.
- `make simrun` 	Run simulator in run-only mode, querying keys in the system.
- `make simulator`	Run the workload simulator (simload + simrun)
```

A simple CLI example:
```
┌ Info: Radish config loaded
│   host = "127.0.0.1"
│   port = 9000
│   shards = 256
└   sync_interval = 5.0
🌱 Connecting to Radish server at radish-server:9000...
✅ Welcome to Radish Server
Type 'HELP' for commands or 'QUIT' to disconnect

RADISH-CLI> KLIST 
✅ [author → string]
RADISH-CLI> S_GET author
✅ https://github.com/fabioscantamburlo
RADISH-CLI> S_SET blog Thanks!
✅ 1
RADISH-CLI> S_GET blog
✅ Thanks!
RADISH-CLI> 
```

That is about it! Every feedback is more than welcome. See you in the next blog post !! 