#include <stdio.h>
#include <sys/io.h>
#include <sys/time.h>

/* Adam's uber-hacky electricity usage monitor */

/* Base address of parallel port */
#define BASE 0x378
/* Flashes per kilowatt hour */
#define PER_KWH 1000.0
/* Number of readings to average */
#define AVG 3

int status = BASE + 1;
int laston = 0;

void wait_change() {
	int on;
	unsigned char v;

	do {
		v = inb(status);
		on = !!(v & 0x20);
		usleep(1000);
	} while (on == laston);
	laston = on;
}

int main(int argc, char **argv) {
	int i;
	long long lasttime = 0;
	double oldvals[AVG];

	if (argc < 2) {
		fprintf(stderr, "usage: readmeter outputfile tempfile\n");
		return 20;
	}

	if (ioperm(BASE, 3, 1) < 0) {
		fprintf(stderr, "ioperm failed\n");
		return 20;
	}

	for (i = 0; i < AVG; i++) oldvals[i] = 0.0;

	wait_change();

	while (1) {
		struct timeval tv;
		long long this, diff;
		double kw;
		int w;
		FILE *f;

		wait_change();
		wait_change();

		gettimeofday(&tv, NULL);
		this = tv.tv_usec + (1000000 * tv.tv_sec);
		diff = this - lasttime;
		lasttime = this;

		if (diff < 250000 || diff > 10000000) continue;

		kw = (3600000000.0 / diff) / PER_KWH;
		for (i = 1; i < AVG; i++) oldvals[i - 1] = oldvals[i];
		oldvals[AVG - 1] = kw;
		kw = 0;
		for (i = 0; i < AVG; i++) kw += oldvals[i];
		kw /= AVG;
		w = kw * 1000;

		f = fopen(argv[2], "w");
		if (f == NULL) {
			fprintf(stderr, "couldn't open %s\n", argv[2]);
			return 20;
		}
		//fprintf(f, "<draw>:<%d>\n", w);
		fprintf(f, "%d\n", w);
		//printf("%d\n", w);
		fclose(f);
		// printf("arguments to rename are: %s %s\n", argv[1], argv[2]);
		if (rename(argv[2], argv[1]) < 0) {
			fprintf(stderr, "couldn't rename file\n");
			return 20;
		}
	}

	return 0;
}

