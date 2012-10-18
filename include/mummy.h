#ifndef _MUMMY_H
#define _MUMMY_H

#include <stdlib.h>

/*
 * platform-specific byte-swapping macros
 */
#include <netinet/in.h>
#if defined(__linux__)
    #include <endian.h>
    #if __BYTE_ORDER == __LITTLE_ENDIAN
        #include <byteswap.h>
        #define htonll(x) bswap_64(x)
        #define ntohll(x) bswap_64(x)
    #else
        #define htonll(x) (x)
        #define ntohll(x) (x)
    #endif
#endif
#if defined(__APPLE__)
    #if __BYTE_ORDER == __LITTLE_ENDIAN
        #include <libkern/OSByteOrder.h>
        #define htonll(x) OSSwapHostToBigInt64(x)
        #define ntohll(x) OSSwapBigToHostInt64(x)
    #else
        #define htonll(x) x
        #define ntohll(x) x
    #endif
    #define bswap_16(x) OSSwapInt16(x)
    #define bswap_32(x) OSSwapInt32(x)
#endif
#if defined(__FreeBSD__)
    #if __BYTE_ORDER == __LITTLE_ENDIAN
        #include <sys/endian.h>
        #define htonll(x) bswap64(x)
        #define ntohll(x) bswap64(x)
    #else
        #define htonll(x) x
        #define ntohll(x) x
    #endif
    #define bswap_16(x) bswap16(x)
    #define bswap_32(x) bswap32(x)
#endif


/*
 * serialized object types
 */
#define MUMMY_TYPE_NULL 0x00
#define MUMMY_TYPE_BOOL 0x01
#define MUMMY_TYPE_CHAR 0x02
#define MUMMY_TYPE_SHORT 0x03
#define MUMMY_TYPE_INT 0x04
#define MUMMY_TYPE_LONG 0x05
#define MUMMY_TYPE_HUGE 0x06
#define MUMMY_TYPE_FLOAT 0x07
#define MUMMY_TYPE_SHORTSTR 0x08
#define MUMMY_TYPE_LONGSTR 0x09
#define MUMMY_TYPE_SHORTUTF8 0x0A
#define MUMMY_TYPE_LONGUTF8 0x0B
#define MUMMY_TYPE_LONGLIST 0x0C
#define MUMMY_TYPE_LONGTUPLE 0x0D
#define MUMMY_TYPE_LONGSET 0x0E
#define MUMMY_TYPE_LONGHASH 0x0F
#define MUMMY_TYPE_SHORTLIST 0x10
#define MUMMY_TYPE_SHORTTUPLE 0x11
#define MUMMY_TYPE_SHORTSET 0x12
#define MUMMY_TYPE_SHORTHASH 0x13
#define MUMMY_TYPE_MEDLIST 0x14
#define MUMMY_TYPE_MEDTUPLE 0x15
#define MUMMY_TYPE_MEDSET 0x16
#define MUMMY_TYPE_MEDHASH 0x17
#define MUMMY_TYPE_MEDSTR 0x18
#define MUMMY_TYPE_MEDUTF8 0x19
#define MUMMY_TYPE_DATE 0x1A
#define MUMMY_TYPE_TIME 0x1B
#define MUMMY_TYPE_DATETIME 0x1C
#define MUMMY_TYPE_TIMEDELTA 0x1D
#define MUMMY_TYPE_DECIMAL 0x1E
#define MUMMY_TYPE_SPECIALNUM 0x1F

#define MUMMY_SPECIAL_INFINITY 0x10
#define MUMMY_SPECIAL_NAN 0x20


/* string with offset */
typedef struct {
    char *data;
    int offset; /* cursor position */
    int len; /* total capacity */
} mummy_string;

mummy_string *mummy_string_new(int);
mummy_string *mummy_string_wrap(char *, int);


/*************
 * reading API
 */
#define mummy_type(str) (str)->data[(str)->offset] & 0x7fffffff
#define mummy_string_space(str) (str)->len - (str)->offset

/* read atoms */
int mummy_read_bool(mummy_string *, char *);
int mummy_read_int(mummy_string *, int64_t *);
int mummy_read_huge(mummy_string *, int, char **, int *);
int mummy_point_to_huge(mummy_string *, char **, int *);
int mummy_read_float(mummy_string *, double *);
int mummy_read_string(mummy_string *, int, char **, int *);
int mummy_point_to_string(mummy_string *, char **, int *);
int mummy_read_utf8(mummy_string *, int, char **, int *);
int mummy_point_to_utf8(mummy_string *, char **, int *);
int mummy_read_decimal(mummy_string *, char *, int16_t *, uint16_t *, char **);
int mummy_read_specialnum(mummy_string *, char *);
int mummy_read_date(mummy_string *, short *, char *, char *);
int mummy_read_time(mummy_string *, char *, char *, char *, int *);
int mummy_read_datetime(mummy_string *, short *, char *, char *,
        char *, char *, char *, int *);
int mummy_read_timedelta(mummy_string *, int *, int *, int *);

/* determine container sizes */
int mummy_container_size(mummy_string *, uint32_t *);

int mummy_string_decompress(mummy_string *, char, char *);

/*************
 * writing API
 */

int mummy_string_makespace(mummy_string *, int);

/* write atoms */
int mummy_feed_null(mummy_string *);
int mummy_feed_bool(mummy_string *, char);
int mummy_feed_int(mummy_string *, int64_t);
int mummy_feed_huge(mummy_string *, char *, int);
int mummy_feed_float(mummy_string *, double);
int mummy_feed_string(mummy_string *, char *, int);
int mummy_feed_utf8(mummy_string *, char *, int);
int mummy_feed_decimal(mummy_string *, char, int16_t, uint16_t, char *);
/*int mummy_feed_va_decimal(mummy_string *, char, uint16_t, uint16_t, ...);*/
int mummy_feed_infinity(mummy_string *, char);
int mummy_feed_nan(mummy_string *, char);
int mummy_feed_date(mummy_string *, unsigned short, char, char);
int mummy_feed_time(mummy_string *, char, char, char, int);
int mummy_feed_datetime(
        mummy_string *, short, char, char, char, char, char, int);
int mummy_feed_timedelta(mummy_string *, int, int, int);

/* open containers (no closing, instead specify length when opening) */
int mummy_open_list(mummy_string *, int);
int mummy_open_tuple(mummy_string *, int);
int mummy_open_set(mummy_string *, int);
int mummy_open_hash(mummy_string *, int);

int mummy_string_compress(mummy_string *);

void mummy_string_free(mummy_string *str, char);

#endif /* _MUMMY_H */
