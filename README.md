Introduction
=============

People! We are all waiting for production version of Redis Cluster.  
But we want to use Redis in production now and we need some failover in it.  

A year ago Redis Sentinel was not able to return falled master into cluster as slave.  
Then I decided to write a small and dumb Redis failover to use in production.  

Redis-replica
=============
So, here it is. Redis-replica is a failover and master election manager for Redis.  
It continuously checks availability of specified Redis nodes.  
Each redis-replica daemon is connected to other redis-replica daemons and exchanges information about pings.  

All redis-replica nodes act equally. So if multiple redis-replica nodes detect a problem all of them try to solve it.  
Redis can handle multiple similar SLAVE OF-commands, so in our case above strategy is normal.  

Redis nodes that are visible from majority of redis-replica nodes are called Quorum-Nodes.  
The counterpart is called Nonquorum-Nodes.  

Several conditions are checked:  

1. No master at all.
2. Multiple masters.
3. Slaves are connected to different masters.
4. Split-brain condition - all nonquorum master turned into slaves.

In the cases 2 and 3 master with more used_memory is elected. It's our production case but can be easily changed.  

Usage
=============

./redis-replica.py < config >

Third-party
=============

[Redis](http://redis.io) first of all.

redis-replica depends on two cool python libraries:
* [python-redis](https://github.com/andymccurdy/redis-py)
* [python-httplib2](http://code.google.com/p/httplib2)
