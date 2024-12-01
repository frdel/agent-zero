#include <stdio.h>
#include <stdlib.h>
#include <bzlib.h>

int main(int argc, char **argv)
{
	if (argc < 2)
	{
		fprintf(stderr, "ERROR: usage bz2 file\n");
		exit(1);
	}

	FILE *fp;
	fp = fopen(argv[1], "r");

	if (NULL == fp)
	{
		fprintf(stderr, "fopen (%s): \n", argv[1]);
		exit(1);
	}

	BZFILE *bzf;
	int bzerror;
	bzf = BZ2_bzReadOpen(&bzerror, fp, 0, 0, NULL, 0);

	if (BZ_OK != bzerror)
	{
		fprintf(stderr, "bzReadOpen (%s): %d\n", argv[1], bzerror);
		exit(1);
	}

	char buf[BUFSIZ];
	int bzRead_r;
	bzRead_r = BZ2_bzRead(&bzerror, bzf, buf, BUFSIZ);

	switch (bzerror)
	{
	case BZ_OK:
	case BZ_STREAM_END:
		printf("%4d/%4d: %.*s\n", bzRead_r, BUFSIZ, bzRead_r, buf);
		break;
	default:
		fprintf(stderr, "bzRead (%s): %d\n", argv[1], bzerror);
		exit(1);
	}

	BZ2_bzReadClose(&bzerror, bzf);

	if (BZ_OK != bzerror)
	{
		fprintf(stderr, "bzReadClose (%s): %d\n", argv[1], bzerror);
		exit(1);
	}

	return 0;
}