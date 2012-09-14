#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#include "lzf.h"
#include "mummy.h"


mummy_string *
mummy_string_new(int initial_buffer) {
    mummy_string *str;

    if (!(str = malloc(sizeof(mummy_string)))) return NULL;
    str->offset = 0;
    str->len = initial_buffer;

    if (initial_buffer && !(str->data = malloc(initial_buffer))) {
        free(str);
        return NULL;
    }
    return str;
}

mummy_string *
mummy_string_wrap(char *buffer, int size) {
    mummy_string *str = mummy_string_new(0);
    str->data = buffer;
    str->len = size;
    return str;
}

int
mummy_string_makespace(mummy_string *str, int size) {
    char *temp;
    int oldlen = str->len;

    while (str->len - str->offset < size) str->len *= 2;

    if (oldlen != str->len) {
        temp = realloc(str->data, str->len);
        if (NULL == temp) {
            str->len = oldlen;
            return 1;
        }
        str->data = temp;
    }

    return 0;
}

/* compress from THE BEGINNING up to the cursor.
   everything after the cursor is thrown away */
int
mummy_string_compress(mummy_string *str) {
    char *output, *temp;
    int compressed;

    /* already been compressed */
    if (str->data[0] & 0x80) return 0;

    /* too small. don't bother compressing, it can't possibly be worth it */
    if (str->offset <= 6) return 0;

    if (!(output = malloc(str->offset - 1))) return ENOMEM;
    if (0 >= (compressed = lzf_compress(str->data + 1, str->offset - 1,
            output + 5, str->offset - 6))) {
        free(output);
        return 0;
    }

    /* realloc the output buffer down to be a snug fit */
    if (compressed < str->offset - 6) {
        temp = realloc(output, compressed + 5);
        if (NULL != temp) output = temp;
    }

    output[0] = str->data[0] | 0x80;
    *(uint32_t *)(output + 1) = htonl(str->offset - 1);
    free(str->data);
    str->data = output;
    str->offset = str->len = compressed + 5;
    return 0;
}

int
mummy_string_decompress(mummy_string *str, char free_buffer, char *rc) {
    uint32_t ucsize;
    char *output;

    *rc = 0;

    /* not compressed */
    if (0 == (str->data[0] & 0x80)) return 0;

    ucsize = ntohl(*(uint32_t *)(str->data + 1));
    if (NULL == (output = malloc(ucsize + 2)))
        return ENOMEM;

    output[0] = str->data[0] & 0x7f;
    if (ucsize != lzf_decompress(
            str->data + 5, str->len - 5, output + 1, ucsize + 1)) {
        if (E2BIG == errno || EINVAL == errno) {
            free(output);
            return errno;
        }
        return -2;
    }

    *rc = 1;
    if (free_buffer) free(str->data);
    str->data = output;
    str->len = ucsize + 1;
    return 0;
}

void
mummy_string_free(mummy_string *str, char also_buffer) {
    if (also_buffer) free(str->data);
    free(str);
}
