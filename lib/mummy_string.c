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

    str->data = malloc(initial_buffer);
    if (!(str->data = malloc(initial_buffer))) {
        free(str);
        return NULL;
    }
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
            output + 5, str->offset - 6)))
        return 0;

    /* realloc the output buffer down to be a snug fit */
    if (compressed < str->offset - 6) {
        temp = realloc(output, compressed);
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
mummy_string_decompress(mummy_string *str) {
    uint32_t ucsize;
    char *output;

    /* not compressed */
    if (0 == (str->data[0] & 0x80)) return 0;

    ucsize = ntohl(*(uint32_t *)(str->data + str->offset + 1));
    output = malloc(ucsize + 1);

    output[0] = str->data[0] & 0x7f;
    if (ucsize != lzf_decompress(
            str->data + 5, str->offset - 5, output, ucsize)) {
        if (E2BIG == errno || EINVAL == errno) {
            free(output);
            return EINVAL;
        }
        return -2;
    }

    free(str->data);
    str->data = output;
    str->len = str->offset = ucsize + 1;
    return 0;
}

int
mummy_string_free(mummy_string *str) {
    free(str->data);
    free(str);
    return 0;
}
