## vtkHyperTreeGridSource distributed support

The HTG Source now supports assigning root-level trees to different distributed pieces in the string descriptor.
For that, prefix refinement letters "." or "R" with a digit to assign it to a distributed piece. The digit prefix acts as a switch, active until another digit is specified.
For example, the descriptor

```
0R.R 1R 0RR 2..R | [...]
```

will assign the first 3 trees to piece 0, the next one to piece 1, the 2 next to piece 0 and the last 3 to piece 2. This logic supports up to 10 different pieces in the descriptor. The digits in the descriptor must match the number of pieces requested from the source.

This also means that it is not possible to use '1' and '0' as replacements for 'R' and '.' as you could do before, even though this feature was not documented.
