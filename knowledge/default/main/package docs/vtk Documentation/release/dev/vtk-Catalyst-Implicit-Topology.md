## Support for Blueprint implicit topology using point set

Catalyst Conduit now supports implicit topology (only points, no cells) using point sets.
The Conduit node has the following entries:
coordsets:
  coords:
    type: "explicit"

topologies:
  mesh:
    type: "points"
    coordset: "coords"
