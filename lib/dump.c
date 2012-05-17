#include <errno.h>
#include <string.h>
#include <stdlib.h>

#include "lzf.h"
#include "mummy.h"

int
mummy_feed_null(mummy_string *str) {
    if (mummy_string_makespace(str, 1)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_NULL;
    return 0;
}

int
mummy_feed_bool(mummy_string *str, char b) {
    if (mummy_string_makespace(str, 2)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_BOOL;
    str->data[str->offset++] = b ? 1 : 0;
    return 0;
}

int
mummy_feed_int(mummy_string *str, int64_t num) {
    char size, type, contents[8];
    memset(contents, 0, 8);

    if (-128 <= num && num < 128) {
        size = 1;
        type = MUMMY_TYPE_CHAR;
        *(&contents[0]) = (int8_t)num;
    } else if (-32768 <= num && num < 32768) {
        size = 2;
        type = MUMMY_TYPE_SHORT;
        *(int16_t *)(&contents[0]) = htons((int16_t)num);
    } else if (-2147483648LL <= num && num < 2147483648LL) {
        size = 4;
        type = MUMMY_TYPE_INT;
        *(int32_t *)(&contents[0]) = htonl((int32_t)num);
    } else {
        size = 8;
        type = MUMMY_TYPE_LONG;
        *(int64_t *)(&contents[0]) = htonll((int64_t)num);
    }

    if (mummy_string_makespace(str, size + 1)) return ENOMEM;
    str->data[str->offset++] = type;
    memcpy(str->data + str->offset, contents, size);
    str->offset += size;

    return 0;
}

int
mummy_feed_huge(mummy_string *str, char *data, int len) {
    if (mummy_string_makespace(str, len + 5)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_HUGE;
    *(uint32_t *)(str->data + str->offset) = htonl(len);
    str->offset += 4;
    memcpy(str->data + str->offset, data, len);
    str->offset += len;
    return 0;
}

int
mummy_feed_float(mummy_string *str, double num) {
    if (mummy_string_makespace(str, 9)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_FLOAT;
    *(uint64_t *)(str->data + str->offset) = htonll(*(uint64_t *)(&num));
    str->offset += 8;
    return 0;
}

int
mummy_feed_string(mummy_string *str, char *data, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTSTR;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDSTR;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGSTR;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    memcpy(str->data + str->offset, data, len);
    str->offset += len;
    return 0;
}

int
mummy_feed_utf8(mummy_string *str, char *data, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTUTF8;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDUTF8;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5 + len)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGUTF8;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    memcpy(str->data + str->offset, data, len);
    str->offset += len;
    return 0;
}

/* decimal encoding:
 * - char of sign (0 positive, 1 negative)
 * - signed short of decimal point position
 * - unsigned short of number of digits
 * - digits (nums 0-9) paired up in bytes, low 4 bits then high 4
 */
int
mummy_feed_decimal(
        mummy_string *str, char is_neg, int16_t exponent, uint16_t count, char *digits) {
    int i;
    char digit;

    if (mummy_string_makespace(str, 6 + (count >> 1) + (count & 1 ? 1 : 0)))
        return ENOMEM;

    str->data[str->offset++] = MUMMY_TYPE_DECIMAL;
    str->data[str->offset++] = is_neg ? 1 : 0;
    *(int16_t *)(str->data + str->offset) = htons(exponent);
    str->offset += 2;
    *(uint16_t *)(str->data + str->offset) = htons(count);
    str->offset += 2;

    for (i = 0; i < count; ++i) {
        digit = digits[i];
        if (digit < 0 || digit > 9) {
            str -> offset -= 5;
            return EINVAL;
        }
        if (i & 1)
            str->data[str->offset + (i >> 1)] |= (uint8_t)(digit << 4);
        else
            str->data[str->offset + (i >> 1)] = (uint8_t)digit;
    }
    str->offset += (count >> 1) + (count & 1 ? 1 : 0);
    return 0;
}

/*
int
mummy_va_feed_decimal(
        mummy_string *str, char is_neg, uint16_t exponent, uint16_t count, ...) {
    va_list arglist;
    int i;
    char digit;

    if (mummy_string_makespace(str, 6 + (count >> 1) + (count & 1 ? 1 : 0)))
            return ENOMEM;

    str->data[str->offset++] = MUMMY_TYPE_DECIMAL;
    str->data[str->offset++] = is_neg ? 2 : 0;
    *(uint16_t *)(str->data + str->offset) = htons(exponent);
    str->offset += 2;
    *(uint16_t *)(str->data + str->offset) = htons(count);
    str->offset += 2;

    va_start(arglist, count);
    for (i = 0; i < count; ++i) {
        digit = va_arg(arglist, char);
        if (digit < 0 || digit > 9) {
            str->offset -= 6;
            return EINVAL;
        }
        str->data[str->offset + 5 + (i >> 1)] = 
            (char)(i & 1 ? digit << 4 : digit);
    }
    va_end(arglist);
    str->offset += (count >> 1) + (count & 1 ? 1 : 0);

    return 0;
}
*/

int
mummy_feed_infinity(mummy_string *str, char is_neg) {
    if (mummy_string_makespace(str, 2)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_SPECIALNUM;
    str->data[str->offset++] = MUMMY_SPECIAL_INFINITY | (is_neg ? 1 : 0);
    return 0;
}

int
mummy_feed_nan(mummy_string *str, char is_snan) {
    if (mummy_string_makespace(str, 2)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_SPECIALNUM;
    str->data[str->offset++] = MUMMY_SPECIAL_NAN | (is_snan ? 1 : 0);
    return 0;
}

int
mummy_feed_date(mummy_string *str, unsigned short year, char month, char day) {
    if (mummy_string_makespace(str, 5)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_DATE;
    *(uint16_t *)(str->data + str->offset) = htons(year);
    str->offset += 2;
    str->data[str->offset++] = month;
    str->data[str->offset++] = day;
    return 0;
}

int
mummy_feed_time(mummy_string *str, char hour, char minute, char second,
        int microsecond) {
    if (mummy_string_makespace(str, 8)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_TIME;
    str->data[str->offset++] = hour;
    str->data[str->offset++] = minute;
    str->data[str->offset++] = second;
    *(uint32_t *)(str->data + str->offset) = htonl(microsecond);
    str->offset += 3;
    return 0;
}

int
mummy_feed_datetime(mummy_string *str, short year, char month, char day,
        char hour, char minute, char second, int microsecond) {
    if (mummy_string_makespace(str, 11)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_DATETIME;
    *(uint16_t *)(str->data + str->offset) = htons(year);
    str->offset += 2;
    str->data[str->offset++] = month;
    str->data[str->offset++] = day;
    str->data[str->offset++] = hour;
    str->data[str->offset++] = minute;
    str->data[str->offset++] = second;
    *(uint32_t *)(str->data + str->offset) = htonl(microsecond);
    str->offset += 3;
    return 0;
}

int
mummy_feed_timedelta(mummy_string *str, int days, int seconds,
        int microseconds) {
    if (mummy_string_makespace(str, 13)) return ENOMEM;
    str->data[str->offset++] = MUMMY_TYPE_TIMEDELTA;
    *(int32_t *)(str->data + str->offset) = htonl(days);
    str->offset += 4;
    *(int32_t *)(str->data + str->offset) = htonl(seconds);
    str->offset += 4;
    *(int32_t *)(str->data + str->offset) = htonl(microseconds);
    str->offset += 4;
    return 0;
}

int
mummy_open_list(mummy_string *str, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTLIST;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDLIST;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGLIST;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    return 0;
}

int
mummy_open_tuple(mummy_string *str, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTTUPLE;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDTUPLE;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGTUPLE;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    return 0;
}

int
mummy_open_set(mummy_string *str, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTSET;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDSET;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGSET;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    return 0;
}

int
mummy_open_hash(mummy_string *str, int len) {
    if (len < 256) {
        if (mummy_string_makespace(str, 2)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_SHORTHASH;
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len;
        str->offset += 1;
    } else if (len < 65536) {
        if (mummy_string_makespace(str, 3)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_MEDHASH;
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len);
        str->offset += 2;
    } else {
        if (mummy_string_makespace(str, 5)) return ENOMEM;
        str->data[str->offset++] = MUMMY_TYPE_LONGHASH;
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len);
        str->offset += 4;
    }
    return 0;
}
