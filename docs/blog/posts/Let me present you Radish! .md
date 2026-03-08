---
date: 2026-03-09
categories:
  - Reinventing the Wheel
  - Tech Deep Dive
---

# I created an in memory key-value DB, let me present you Radish! 

Hello! This is my first **"real"** article. Today's topic is about building your own in memory key-value DB. 
The reasons behind this choice is simple: **I wanted to understand better what an in memory db is**.
I always heard good words spent on Redis (and its creator) so I thought: What's the best way of learning a tool? - Creating it one similar!
Follow the article to see how it went! (Spoiler: surpisingly good)
<!-- more -->

# What Radish is? (more broadly what is a key-value DB)
As I said Radish is an experimental project, we can also say a didactical project, aimed to re implement a key-value in memory DB. 
So if you already know Redis/Valkey you may have familiarity with this concept, otherwise you can think about them as shared data-structures cache, accessible to clients around the web. (you can also imagine it as a giant python dictionary accessible on the web that supports several data-structures as values)
The concept evolved significantly from this definitions, but if we refer to the core idea, still I think this is the best definition out there.
This is useful when you have data to share from producers to consumers (not limited to) that is not "easily" shared using a standard sql DB table, for instance lists. 

Going trough all the Radish implementation is a long and exausting exercise that you can do, if you are curious, reading the documentation.
In this blog article I just want to summarize few concepts that I loved while implementing it, hopefully you will love them too, or at least learn/enjoy. 

***P.S. Radish is implemented in Julia, don't ask me why because I don't know! (I like the name)***


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
    datatype::Symbol # Datatype simbol to efficiently look up the type
end
```
The core most importation decision is to build Radish using a delegation pattern. 
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

Adding a new type is easy because you rely on already defined **Hypercommands**, you just have to implement specific data types functio, in other words hypercommands provide a standardize way to access the RadishContext.

There are a lot of **Hypercommands** that support a lot of interfaces: get, add, modify, delete, get and modify, etc. The full list is [Here ](?/architecture.html#example-how-s_get-works).

### S_GET example
To explain further this idea, let's take a look at the command `S_GET` the most simple command you can operate on `strings`, defined in the string palette above.

Whenever the client calls for an `S_GET` command, using lookup we know it must be routed to: `(sget, rget_or_expire!)`.

This means we are calling `rget_or_expire!` on the whole RadishContext which delegates the real get operation to the `sget` function. [Docs example](?/architecture.html#example-how-s_get-works).


# 2 - Sharded locks - how to handle concurrency
First of all, Radish is multi-threaded. This means that multiple clients are served concurrently, which requires explicit synchronization.
This was a deliberate choice from me. On top of that I think that understanding concurrency primitives is essential for systems engineering, and Radish is a good gym to explore them.

When multiple clients access shared state concurrently, bad things can happen:

```
Client A: reads counter = 10
Client B: reads counter = 10
Client A: writes counter = 11
Client B: writes counter = 11    ← Should be 12!
```

This is a **race condition** — the classic lost-update problem. A good system needs to prevent this!

The first idea is hide every variable (RadishElement) behind a lock. Everytime you need to read it the system acquires the lock on that element. This prevents every other process to read or write. As you may feel, this is a good idea because the system will be safe but it will make it very slow.

Every objects has its own lock, that has to be locked/unlocked (what if I have 1M objects?) plus some operations are not really requiring a lock like the read.

To solve this I decided to use a **Sharded-Writeonly-Lock** implementation. It works as follows:

- Each key object is hashed into a smaller space. I used 256 spaces - they are called **shards**.
- Every time you want to perform a write operation (**Hypercommands**: rmodify, rdelete, ...) the system acquires the lock on the whole shard. 
- It does the modification, and eventually it releases the lock.

Pros: 
- Limited amount of locks to manage.
- Lock free reads.

Cons:
- Locking N/256 keys together.

Of course this is not (possibly) the best design choice, it heavily depends on how read intensive / write intensive your usage is and many others complex factors. I just want to remark this is not a simple problem and that's why I loved it. I could only imagine tons of decisions like this when building complex systems. **Kudos** to all the developers around.

# 3 - Time To Live, deleting expired keys.

This is a common problem when you have an expire policy. You have some keys that are valid up to a certain time, then those are not anymore available and you have to delete it.
The naive way is to loop on all the keys every *t* milliseconds and check every element. This may be a bad idea computationally speaking, so there are two very pragmatic strategies to handle this. 

1) **Deletion on lookup a.k.a lazy deletion**

Very simple, the system doesn't do anything. When an operation on the key is perfomed the first check is validity. If the key is not valid anymore just delete it and act like the key is not present in the DB.

Altought this is a very valid idea, you may have situations in which a key with a TTL is created and never accessed. It will never be deleted if you use this method only.

2) **Random deletion a.k.a active deletion**

Another cool method is to have a random process that randomly subsamples keys and performs the active check. In case of positive answer it deletes the key. This process needs to be tuned otherwise the risk is to have a lot of locks / computation power invested in keeping the DB clean and not serving clients.

Radish combines the two deletions strategies with a more smart implementation for the active part that runs every `t` seconds, in particular the workflow is the following:
- It samples 10% of the keys randomly
- It order the keys into shards
- It performs a per-shard locking — it locks one shard at a time, checks only the sampled keys in that shard, and moves on.

This minimizes the time any single shard is locked. Theoretically increasing the reactivness of the system.


# 4 - Persistence - last topic for this blog post :/