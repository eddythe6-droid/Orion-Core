# Resource ownership model (simulation)

`ResourceOwnershipTracker` records which named queue most recently owns a
resource. Initial acquisition has no prior owner; subsequent handoffs require
a fence dependency associated with the previous owner queue. The tracker
rejects handoffs without a dependency, dependencies from the wrong queue,
duplicate registrations, and redundant same-owner transfers.

This is deliberately bookkeeping, not a D3D12 ownership-transfer primitive.
D3D12 resource barriers and queue synchronization have more nuanced rules;
the tracker does not execute barriers, submit queue waits, or prove memory
visibility. It is used alongside the manager's fence dependency model to make
ownership assumptions visible in test reports.
