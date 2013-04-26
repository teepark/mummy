
#define mummy_open_short(str, len, type)                      \
    do { mummy_string_makespace(str, 2);                      \
        str->data[str->offset++] = type;                      \
        *(uint8_t *)(str->data + str->offset) = (uint8_t)len; \
        str->offset += 1; } while (0)

#define mummy_open_med(str, len, type)                                 \
    do { mummy_string_makespace(str, 3);                               \
        str->data[str->offset++] = type;                               \
        *(uint16_t *)(str->data + str->offset) = htons((uint16_t)len); \
        str->offset += 2; } while (0)

#define mummy_open_long(str, len, type)                                \
    do { mummy_string_makespace(str, 5);                               \
        str->data[str->offset++] = type;                               \
        *(uint32_t *)(str->data + str->offset) = htonl((uint32_t)len); \
        str->offset += 4; } while (0)
