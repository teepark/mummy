#include <errno.h>
#include <string.h>

#include "lzf.h"
#include "mummy.h"


int
mummy_read_bool(mummy_string *str, char *result) {
    if (mummy_string_space(str) < 2) return -1;
    *result = str->data[str->offset + 1] ? 1 : 0;
    str->offset += 2;
    return 0;
}

int
mummy_read_int(mummy_string *str, int64_t *result) {
    if (mummy_string_space(str) < 1) return -1;

    switch (str->data[str->offset++]) {
    case MUMMY_TYPE_CHAR:
        if (mummy_string_space(str) < 1) return -1;
        *result = (int64_t)(*(int8_t *)(str->data + str->offset));
        str->offset += 1;
        return 0;
    case MUMMY_TYPE_SHORT:
        if (mummy_string_space(str) < 2) return -1;
        *result = (int16_t)ntohs(*(int16_t *)(str->data + str->offset));
        str->offset += 2;
        return 0;
    case MUMMY_TYPE_INT:
        if (mummy_string_space(str) < 4) return -1;
        *result = (int32_t)ntohl(*(int32_t *)(str->data + str->offset));
        str->offset += 4;
        return 0;
    case MUMMY_TYPE_LONG:
        if (mummy_string_space(str) < 8) return -1;
        *result = ntohll(*(int64_t *)(str->data + str->offset));
        str->offset += 8;
        return 0;
    }
    return -2;
}

int
mummy_read_huge(mummy_string *str, int upto,
        char **result, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 5) return -1;

    len = ntohl(*(uint32_t *)(str->data + str->offset + 1));
    if (mummy_string_space(str) - 5 < len) return -1;
    *result_len = len;
    if (len > upto) return -3;
    memcpy(*result, str->data + str->offset + 5, len);
    str->offset += len + 5;
    return 0;
}

int
mummy_point_to_huge(mummy_string *str, char **buf, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 5) return -1;

    len = ntohl(*(uint32_t *)(str->data + str->offset + 1));
    if (mummy_string_space(str) - 5 < len) return -1;
    *result_len = len;
    *buf = str->data + str->offset + 5;
    str->offset += len + 5;
    return 0;
}

int
mummy_read_float(mummy_string *str, double *result) {
    uint64_t output;

    if (mummy_string_space(str) < 9) return -1;

    output = ntohll(*(uint64_t *)(str->data + str->offset + 1));
    *result = *(double *)&output;
    str->offset += 9;
    return 0;
}

int
mummy_read_string(mummy_string *str, int upto, char **result, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 1) return -1;

    switch(str->data[str->offset++]) {
    case MUMMY_TYPE_SHORTSTR:
        if (mummy_string_space(str) < 1) return -1;
        len = (uint32_t)(*(uint8_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 1 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 1, len);
        str->offset += len + 1;
        return 0;
    case MUMMY_TYPE_MEDSTR:
        if (mummy_string_space(str) < 2) return -1;
        len = (uint32_t)ntohs(*(uint16_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 2 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 2, len);
        str->offset += len + 2;
        return 0;
    case MUMMY_TYPE_LONGSTR:
        if (mummy_string_space(str) < 4) return -1;
        len = ntohl(*(uint32_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 4 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 4, len);
        str->offset += len + 4;
        return 0;
    }
    return -2;
}

int
mummy_point_to_string(mummy_string *str, char **target, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 1) return -1;

    switch(str->data[str->offset++]) {
    case MUMMY_TYPE_SHORTSTR:
        if (mummy_string_space(str) < 1) return -1;
        len = (uint32_t)(*(uint8_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 1 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 1;
        str->offset += len + 1;
        return 0;
    case MUMMY_TYPE_MEDSTR:
        if (mummy_string_space(str) < 2) return -1;
        len = (uint32_t)ntohs(*(uint16_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 2 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 2;
        str->offset += len + 2;
        return 0;
    case MUMMY_TYPE_LONGSTR:
        if (mummy_string_space(str) < 4) return -1;
        len = ntohl(*(uint32_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 4 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 4;
        str->offset += len + 4;
        return 0;
    }
    return -2;
}

int
mummy_read_utf8(mummy_string *str, int upto, char **result, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 1) return -1;

    switch(str->data[str->offset++]) {
    case MUMMY_TYPE_SHORTUTF8:
        if (mummy_string_space(str) < 1) return -1;
        len = (uint32_t)(*(uint8_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 1 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 1, len);
        str->offset += len + 1;
        return 0;
    case MUMMY_TYPE_MEDUTF8:
        if (mummy_string_space(str) < 2) return -1;
        len = (uint32_t)ntohs(*(uint16_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 2 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 2, len);
        str->offset += len + 2;
        return 0;
    case MUMMY_TYPE_LONGUTF8:
        if (mummy_string_space(str) < 4) return -1;
        len = ntohl(*(uint32_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 4 < len) return -1;
        *result_len = len;
        if (len > upto) return -3;
        memcpy(*result, str->data + str->offset + 4, len);
        str->offset += len + 4;
        return 0;
    }
    return -2;
}

int
mummy_point_to_utf8(mummy_string *str, char **target, int *result_len) {
    uint32_t len;

    if (mummy_string_space(str) < 1) return -1;

    switch(str->data[str->offset++]) {
    case MUMMY_TYPE_SHORTUTF8:
        if (mummy_string_space(str) < 1) return -1;
        len = (uint32_t)(*(uint8_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 1 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 1;
        str->offset += len + 1;
        return 0;
    case MUMMY_TYPE_MEDUTF8:
        if (mummy_string_space(str) < 2) return -1;
        len = ntohs(*(uint16_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 2 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 2;
        str->offset += len + 2;
        return 0;
    case MUMMY_TYPE_LONGUTF8:
        if (mummy_string_space(str) < 4) return -1;
        len = ntohl(*(uint32_t *)(str->data + str->offset));
        if (mummy_string_space(str) - 4 < len) return -1;
        *result_len = len;
        *target = str->data + str->offset + 4;
        str->offset += len + 4;
        return 0;
    }
    return -2;
}

int
mummy_read_decimal(mummy_string *str,
        char *sign, int16_t *exponent, uint16_t *count, char **digits) {
    uint16_t dsize, bytes;
    int16_t dexpo;
    int i;
    unsigned char c;

    if (mummy_string_space(str) < 6) return -1;

    /* regular decimal number */
    dexpo = ntohs(*(int16_t *)(str->data + str->offset + 2));
    dsize = ntohs(*(uint16_t *)(str->data + str->offset + 4));
    bytes = (dsize >> 1) + (dsize & 1 ? 1 : 0);

    if (mummy_string_space(str) - 6 < bytes) return -1; /* TODO: wat is this */
    if (!(*digits = malloc(dsize))) return ENOMEM;

    *sign = str->data[str->offset + 1] ? 1 : 0;
    *exponent = dexpo;
    *count = dsize;
    str->offset += 6;

    for (i = 0; i < dsize; ++i) {
        c = str->data[str->offset + (i>>1)];
        if (i & 1) /* odd, get the high 4 bits */
            c = 0 | (c >> 4);
        else /* even, get the low 4 bits */
            c = c & 0x0f;
        (*digits)[i] = c;
    }
    str->offset += bytes;
    return 0;
}

int
mummy_read_specialnum(mummy_string *str, char *flags) {
    if (mummy_string_space(str) < 2) return -1;
    *flags = str->data[str->offset + 1];
    str->offset += 2;
    return 0;
}

int
mummy_read_date(mummy_string *str, short *year, char *month, char *day) {
    if (mummy_string_space(str) < 5) return -1;
    *year = ntohs(*(uint16_t *)(str->data + str->offset + 1));
    *month = *(uint8_t *)(str->data + str->offset + 3);
    *day = *(uint8_t *)(str->data + str->offset + 4);
    str->offset += 5;
    return 0;
}

int
mummy_read_time(mummy_string *str,
        char *hour, char *minute, char *second, int *microsecond) {
    if (mummy_string_space(str) < 7) return -1;
    *hour = *(uint8_t *)(str->data + str->offset + 1);
    *minute = *(uint8_t *)(str->data + str->offset + 2);
    *second = *(uint8_t *)(str->data + str->offset + 3);
    *microsecond = ntohl(*(uint32_t *)(str->data + str->offset + 4) << 8);
    str->offset += 7;
    return 0;
}

int
mummy_read_datetime(mummy_string *str, short *year, char *month, char *day,
        char *hour, char *minute, char *second, int *microsecond) {
    if (mummy_string_space(str) < 11) return -1;
    *year = ntohs(*(uint16_t *)(str->data + str->offset + 1));
    *month = *(uint8_t *)(str->data + str->offset + 3);
    *day = *(uint8_t *)(str->data + str->offset + 4);
    *hour = *(uint8_t *)(str->data + str->offset + 5);
    *minute = *(uint8_t *)(str->data + str->offset + 6);
    *second = *(uint8_t *)(str->data + str->offset + 7);
    *microsecond = ntohl(*(uint32_t *)(str->data + str->offset + 8) << 8);
    str->offset += 11;
    return 0;
}

int
mummy_read_timedelta(mummy_string *str, int *days, int *seconds,
        int *microseconds) {
    if (mummy_string_space(str) < 13) return -1;
    *days = ntohl(*(int32_t *)(str->data + str->offset + 1));
    *seconds = ntohl(*(int32_t *)(str->data + str->offset + 5));
    *microseconds = ntohl(*(int32_t *)(str->data + str->offset + 9));
    str->offset += 13;
    return 0;
}

int
mummy_container_size(mummy_string *str, uint32_t *result) {
    switch (mummy_type(str)) {
    case MUMMY_TYPE_SHORTLIST:
    case MUMMY_TYPE_SHORTTUPLE:
    case MUMMY_TYPE_SHORTHASH:
    case MUMMY_TYPE_SHORTSET:
        if (mummy_string_space(str) < 2) return -1;
        *result = (uint32_t)*(uint8_t *)(str->data + str->offset + 1);
        str->offset += 2;
        return 0;
    case MUMMY_TYPE_MEDLIST:
    case MUMMY_TYPE_MEDTUPLE:
    case MUMMY_TYPE_MEDHASH:
    case MUMMY_TYPE_MEDSET:
        if (mummy_string_space(str) < 3) return -1;
        *result = (uint32_t)ntohs(*(uint16_t *)(str->data + str->offset + 1));
        str->offset += 3;
        return 0;
    case MUMMY_TYPE_LONGLIST:
    case MUMMY_TYPE_LONGTUPLE:
    case MUMMY_TYPE_LONGHASH:
    case MUMMY_TYPE_LONGSET:
        if (mummy_string_space(str) < 5) return -1;
        *result = ntohl(*(uint32_t *)(str->data + str->offset + 1));
        str->offset += 5;
        return 0;
    }
    return -1;
}
