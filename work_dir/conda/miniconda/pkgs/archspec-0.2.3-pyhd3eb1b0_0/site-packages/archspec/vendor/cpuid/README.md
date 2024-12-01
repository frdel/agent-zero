cpuid.py
========

Now, this is silly!

Pure Python library for accessing information about x86 processors
by querying the [CPUID](http://en.wikipedia.org/wiki/CPUID)
instruction. Well, not exactly pure Python...

It works by allocating a small piece of virtual memory, copying
a raw x86 function to that memory, giving the memory execute
permissions and then calling the memory as a function. The injected
function executes the CPUID instruction and copies the result back
to a ctypes.Structure where is can be read by Python.

It should work fine on both 32 and 64 bit versions of Windows and Linux
running x86 processors. Apple OS X and other BSD systems should also work,
not tested though...


Why?
----
For poops and giggles. Plus, having access to a low-level feature
without having to compile a C wrapper is pretty neat.


Examples
--------
Getting info with eax=0:

    import cpuid

    q = cpuid.CPUID()
    eax, ebx, ecx, edx = q(0)

Running the files:

    $ python example.py 
    Vendor ID : GenuineIntel
    CPU name  : Intel(R) Xeon(R) CPU           W3550  @ 3.07GHz
    
    Vector instructions supported:
    SSE       : Yes
    SSE2      : Yes
    SSE3      : Yes
    SSSE3     : Yes
    SSE4.1    : Yes
    SSE4.2    : Yes
    SSE4a     : --
    AVX       : --
    AVX2      : --
    
    $ python cpuid.py
    CPUID    A        B        C        D
    00000000 0000000b 756e6547 6c65746e 49656e69
    00000001 000106a5 00100800 009ce3bd bfebfbff
    00000002 55035a01 00f0b2e4 00000000 09ca212c
    00000003 00000000 00000000 00000000 00000000
    00000004 00000000 00000000 00000000 00000000
    00000005 00000040 00000040 00000003 00001120
    00000006 00000003 00000002 00000001 00000000
    00000007 00000000 00000000 00000000 00000000
    00000008 00000000 00000000 00000000 00000000
    00000009 00000000 00000000 00000000 00000000
    0000000a 07300403 00000044 00000000 00000603
    0000000b 00000000 00000000 00000095 00000000
    80000000 80000008 00000000 00000000 00000000
    80000001 00000000 00000000 00000001 28100800
    80000002 65746e49 2952286c 6f655820 2952286e
    80000003 55504320 20202020 20202020 57202020
    80000004 30353533 20402020 37302e33 007a4847
    80000005 00000000 00000000 00000000 00000000
    80000006 00000000 00000000 01006040 00000000
    80000007 00000000 00000000 00000000 00000100
    80000008 00003024 00000000 00000000 00000000

