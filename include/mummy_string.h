#ifndef _MUMMY_STRING_H
#define _MUMMY_STRING_H

/* string with offset */
typedef struct {
    char *data;
    int offset; /* cursor position */
    int len; /* total capacity */
} mummy_string;

mummy_string *mummy_string_new(int);
mummy_string *mummy_string_wrap(char *, int);
void mummy_string_free(mummy_string *str, char);

#define mummy_string_space(str) (str)->len - (str)->offset

/* using a macro instead to see if it speeds things up
int mummy_string_makespace(mummy_string *, int);
*/
#define mummy_string_makespace(str, size)                     \
    char *temp; int oldlen;                                   \
    if (str->len - str->offset < size) {                      \
        oldlen = str->len;                                    \
        while (str->len - str->offset < size) str->len <<= 1; \
        temp = realloc(str->data, str->len);                  \
        if (NULL == temp) {                                   \
            str->len = oldlen;                                \
            return ENOMEM;                                    \
        }                                                     \
        str->data = temp;                                     \
    }

int mummy_string_compress(mummy_string *);
int mummy_string_decompress(mummy_string *, char, char *);

#endif /* _MUMMY_STRING_H */
