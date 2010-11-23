#include "Python.h"
#include <netinet/in.h>

#include "lzf.h"


/*
 * platform-specific byte-swapping macros
 */
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
#endif


/*
 * python 2.4 has come C API holes
 */
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
    #define Py_ssize_t ssize_t
    #define PySet_GET_SIZE(s) PyDict_Size(((PySetObject *)s)->data)
    #define PySet_MINSIZE 8
#endif


/*
 * there are major C-API changes in python 3+
 */
#if PY_MAJOR_VERSION >= 3
    #define IS_PYTHON3
#endif


/*
 * serialized object types
 */
#define TYPE_NONE 0x00
#define TYPE_BOOL 0x01
#define TYPE_CHAR 0x02
#define TYPE_SHORT 0x03
#define TYPE_INT 0x04
#define TYPE_LONG 0x05
#define TYPE_HUGE 0x06
#define TYPE_DOUBLE 0x07
#define TYPE_SHORTSTR 0x08
#define TYPE_LONGSTR 0x09
#define TYPE_SHORTUTF8 0x0A
#define TYPE_LONGUTF8 0x0B
#define TYPE_LIST 0x0C
#define TYPE_TUPLE 0x0D
#define TYPE_SET 0x0E
#define TYPE_DICT 0x0F

#define TYPE_SHORTLIST 0x10
#define TYPE_SHORTTUPLE 0x11
#define TYPE_SHORTSET 0x12
#define TYPE_SHORTDICT 0x13


#define MAX_DEPTH 256
#define INITIAL_BUFFER_SIZE 0x1000

typedef struct offsetstring {
    char *data;
    int offset; /* amount full */
    int length; /* total capacity */
} offsetstring;

#define HAS_SPACE(str,l) if ((str)->length - (str)->offset < l) {\
                             PyErr_SetString(PyExc_ValueError,\
                                     "invalid mummy (incorrect length)");\
                             return NULL;\
                         }

static int
ensure_space(offsetstring *string, long length) {
    if (string->length - string->offset < length) {
        while (string->length - string->offset < length) string->length *= 2;
        string->data = (char *)realloc(string->data, string->length);
        if (string->data == NULL) {
            PyErr_SetString(PyExc_MemoryError, "failed to reallocate");
            return ENOMEM;
        }
    }
    return 0;
}


#define BREAKOUT(obj) { Py_DECREF(obj); obj = NULL; break; }


static int
dump_one(PyObject *obj, offsetstring *string, PyObject *default_handler,
        int depth) {
    register int rc;
    int i;
#ifndef IS_PYTHON3
    register long l;
#endif
    register long long ll;
    register size_t t;
    uint64_t ui;

    Py_ssize_t pst;
    PyObject *iterator, *key, *value, *handler_args;

    if (depth > MAX_DEPTH) {
        PyErr_SetString(
                PyExc_ValueError, "maximum depth exceeded");
        return -1;
    }

    if (default_handler != Py_None && !PyCallable_Check(default_handler)) {
        PyErr_SetString(PyExc_TypeError, "default must be callable or None");
        return -1;
    }

    if (obj == Py_None) {
        /*
         * None gets no header OR body
         * TYPE_NONE is enough of a description
         */
        rc = ensure_space(string, 1);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_NONE;
        return 0;
    }
    if (PyBool_Check(obj)) {
        /*
         * booleans get the type TYPE_BOOL and 1 more byte
         * (though they only need 1 more *bit*)
         */
        rc = ensure_space(string, 2);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_BOOL;
        string->data[string->offset++] = obj == Py_True;
        return 0;
    }
#ifndef IS_PYTHON3
    if (PyInt_CheckExact(obj)) {
        l = PyInt_AS_LONG(obj);

        if (-128 <= l && l < 128) {
            /*
             * integer that fits in 1 byte
             * no header (TYPE_CHAR is known to be 1 byte)
             */
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_CHAR;
            string->data[string->offset++] = (int8_t)l;
            return 0;
        }
        if (-32768 <= l && l < 32768) {
            /*
             * fits in 2 bytes
             * no header (TYPE_SHORT is known to be 2 bytes)
             */
            rc = ensure_space(string, 3);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORT;
            *(int16_t *)(string->data + string->offset) = htons((int16_t)l);
            string->offset += 2;
            return 0;
        }
        if (-2147483648LL <= l && l < 2147483648LL){
            /*
             * fits in 4 bytes
             * no header (TYPE_INT is known to be 4 bytes)
             */
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_INT;
            *(int32_t *)(string->data + string->offset) = htonl((int32_t)l);
            string->offset += 4;
            return 0;
        }

        /*
         * it has to fit in 8 bytes, otherwise it wouldn't be a PyInt.
         * no header, TYPE_LONG is always 8 more bytes
         */
        rc = ensure_space(string, 9);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_LONG;
        *(int64_t *)(string->data + string->offset) = htonll((int64_t)l);
        string->offset += 8;
        return 0;
    }
#endif
    if (PyLong_CheckExact(obj)) {
        ll = PyLong_AsLongLong(obj);

        if (ll == -1 && PyErr_Occurred()) {
            PyErr_Clear();
            /*
             * doesn't fit in a 64 bit int, so TYPE_HUGE
             * 4-byte unsigned header for the length of the rest
             * the *rest* is a base-256 signed integer
             */
            t = _PyLong_NumBits(obj) + 1; /* one more bit for the sign */
            t = t & 0x7 ? (t >> 3) + 1 : t >> 3;
            rc = ensure_space(string, t + 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_HUGE;
            *(uint32_t *)(string->data + string->offset) = htonl(t);
            string->offset += 4;
            rc = _PyLong_AsByteArray((PyLongObject *)obj,
                    (unsigned char *)(string->data + string->offset), t, 0, 1);
            string->offset += t;
            if (rc) return rc;
            return 0;
        }
        if (-128 <= ll && ll < 128){
            /*
             * PyLong that fits in 1 byte
             */
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_CHAR;
            string->data[string->offset++] = (int8_t)ll;
            return 0;
        }
        if (-32768 <= ll && ll < 32768) {
            /*
             * PyLong that fits in 2 bytes
             */
            rc = ensure_space(string, 3);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORT;
            *(int16_t *)(string->data + string->offset) = htons((int16_t)ll);
            string->offset += 2;
            return 0;
        }
        if (-2147483648LL <= ll && ll < 2147483648LL) {
            /*
             * PyLong that fits in 4 bytes
             */
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_INT;
            *(int32_t *)(string->data + string->offset) = htonl((int32_t)ll);
            string->offset += 4;
            return 0;
        }

        /*
         * PyLong that fits in 8 bytes
         * use TYPE_LONG like above
         */
        rc = ensure_space(string, 9);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_LONG;
        *(int64_t *)(string->data + string->offset) = htonll(ll);
        string->offset += 8;
        return 0;
    }
    if (PyFloat_CheckExact(obj)) {
        /*
         * PyFloats are stored as 8 byte doubles
         * so no header, TYPE_DOUBLE says it all
         */
        rc = ensure_space(string, 9);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_DOUBLE;
        ui = htonll(*(uint64_t *)(&PyFloat_AS_DOUBLE(obj)));
        *(double *)(string->data + string->offset) = *(double *)(&ui);
        string->offset += 8;
        return 0;
    }
#ifdef IS_PYTHON3
    if (PyBytes_CheckExact(obj)) {
#else
    if (PyString_CheckExact(obj)) {
#endif
        /*
         * PyStrings/PyBytes get a 1-byte header if they fit in 256 bytes,
         * otherwise a 4-byte header (TYPE_SHORTSTR or TYPE_LONGSTR)
         */
#ifdef IS_PYTHON3
        pst = PyBytes_GET_SIZE(obj);
#else
        pst = PyString_GET_SIZE(obj);
#endif
        if (pst < 256) {
            rc = ensure_space(string, pst + 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTSTR;
            *(uint8_t *)(string->data + string->offset++) = (uint8_t)pst;
#ifdef IS_PYTHON3
            memcpy(string->data + string->offset, PyBytes_AS_STRING(obj), pst);
#else
            memcpy(string->data + string->offset, PyString_AS_STRING(obj), pst);
#endif
            string->offset += pst;
            return 0;
        }

        rc = ensure_space(string, pst + 5);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_LONGSTR;
        *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
        string->offset += 4;
#ifdef IS_PYTHON3
        memcpy(string->data + string->offset, PyBytes_AS_STRING(obj), pst);
#else
        memcpy(string->data + string->offset, PyString_AS_STRING(obj), pst);
#endif
        string->offset += pst;
        return 0;
    }
    if (PyUnicode_CheckExact(obj)) {
        /*
         * PyUnicodes get encoded utf8 and then handled just like PyStrings
         * there is a separate type for <256 bytes, and they get a 1 or 4 byte
         * header (TYPE_SHORTUTF8 or TYPE_LONGUTF8)
         */
        obj = PyUnicode_AsUTF8String(obj);
#ifdef IS_PYTHON3
        pst = PyBytes_GET_SIZE(obj);
#else
        pst = PyString_GET_SIZE(obj);
#endif
        if (pst < 256) {
            rc = ensure_space(string, pst + 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTUTF8;
            *(uint8_t *)(string->data + string->offset) = (uint8_t)pst;
#ifdef IS_PYTHON3
            memcpy(string->data + string->offset + 1, PyBytes_AS_STRING(obj),
                    pst);
#else
            memcpy(string->data + string->offset + 1, PyString_AS_STRING(obj),
                    pst);
#endif
            string->offset += pst + 1;
            return 0;
        }

        rc = ensure_space(string, pst + 5);
        if (rc) return rc;
        string->data[string->offset++] = TYPE_LONGUTF8;
        *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
#ifdef IS_PYTHON3
        memcpy(string->data + string->offset + 4, PyBytes_AS_STRING(obj),
                pst);
#else
        memcpy(string->data + string->offset + 4, PyString_AS_STRING(obj),
                pst);
#endif
        string->offset += pst + 4;
        return 0;
    }
    if (PyList_CheckExact(obj)) {
        /*
         * PyList gets a 1-byte or 4-byte unsigned header (TYPE_SHORTLIST
         * or TYPE_LIST) containing the number of elements (not bytes)
         */
        pst = PyList_GET_SIZE(obj);
        if (pst < 256) {
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTLIST;
            *(uint8_t *)(string->data + string->offset++) = (uint8_t)pst;
        }
        else {
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_LIST;
            *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
            string->offset += 4;
        }
        for (i = 0; i < pst; i++) {
            value = PyList_GET_ITEM(obj, i);
            if (dump_one(value, string, default_handler, depth + 1))
                return -1;
        }
        return 0;
    }
    if (PyTuple_CheckExact(obj)) {
        /*
         * PyTuple handling is just like PyList
         * except the type is TYPE_[SHORT]TUPLE
         */
        pst = PyTuple_GET_SIZE(obj);
        if (pst < 256) {
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTTUPLE;
            *(uint8_t *)(string->data + string->offset++) = (uint8_t)pst;
        }
        else {
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_TUPLE;
            *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
            string->offset += 4;
        }
        for (i = 0; i < pst; i++) {
            value = PyTuple_GET_ITEM(obj, i);
            if (dump_one(value, string, default_handler, depth + 1)) return -1;
        }
        return 0;
    }
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
    if (PyAnySet_Check(obj)) {
#else
    if (PyAnySet_CheckExact(obj)) {
#endif
        /*
         * PySets have a type TYPE_[SHORT]SET but
         * otherwise are encoded like PyLists
         */
        pst = PySet_GET_SIZE(obj);
        if (pst < 256) {
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTSET;
            *(uint8_t *)(string->data + string->offset++) = (uint8_t)pst;
        }
        else {
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SET;
            *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
            string->offset += 4;
        }

        iterator = PyObject_GetIter(obj);
        while ((value = PyIter_Next(iterator))) {
            rc = dump_one(value, string, default_handler, depth + 1);
            Py_XDECREF(value);
            if (rc) break;
        }
        Py_XDECREF(iterator);
        if (rc) return -1;
        return 0;
    }
    if (PyDict_CheckExact(obj)) {
        /*
         * PyDicts have type TYPE_DICT, get a 4-byte header with the number of
         * children, and have their own protocol for iteration
         */
        pst = PyDict_Size(obj);
        if (pst < 256) {
            rc = ensure_space(string, 2);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_SHORTDICT;
            *(uint8_t *)(string->data + string->offset++) = (uint8_t)pst;
        }
        else {
            rc = ensure_space(string, 5);
            if (rc) return rc;
            string->data[string->offset++] = TYPE_DICT;
            *(uint32_t *)(string->data + string->offset) = htonl((uint32_t)pst);
            string->offset += 4;
        }

        pst = 0;
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
        while (PyDict_Next(obj, &i, &key, &value)) {
#else
        while (PyDict_Next(obj, &pst, &key, &value)) {
#endif
            if (dump_one(key, string, default_handler, depth + 1)) return -1;
            if (dump_one(value, string, default_handler, depth + 1)) return -1;
        }
        return 0;
    }

    if (default_handler != Py_None) {
        // give our obj reference to default_handler
        handler_args = PyTuple_New(1);
        PyTuple_SET_ITEM(handler_args, 0, obj);
        obj = PyObject_Call(default_handler, handler_args, NULL);
        // don't increment depth, but don't pass on default_handler either
        return dump_one(obj, string, Py_None, depth);
    }

    PyErr_SetString(PyExc_TypeError, "unserializable type");
    return -1;
}


static PyObject *
load_one(offsetstring *string, char intern) {
    unsigned int i;
    register uint32_t size;
    uint64_t ll;
    PyObject *obj = NULL,
             *key,
             *value;

    if (!(string->length - string->offset)) {
        PyErr_SetString(PyExc_ValueError, "no data from which to load");
        return NULL;
    }

    switch(string->data[string->offset++]) {
    case TYPE_NONE:
        obj = Py_None;
        Py_XINCREF(obj);
        break;
    case TYPE_BOOL:
        HAS_SPACE(string, 1);
        obj = string->data[string->offset++] ? Py_True : Py_False;
        Py_XINCREF(obj);
        break;
    case TYPE_CHAR:
        HAS_SPACE(string, 1);
#ifdef IS_PYTHON3
        obj = PyLong_FromLong(*(int8_t *)(string->data + string->offset++));
#else
        obj = PyInt_FromLong(*(int8_t *)(string->data + string->offset++));
#endif
        break;
    case TYPE_SHORT:
        HAS_SPACE(string, 2);
#ifdef IS_PYTHON3
        obj = PyLong_FromLong((int16_t)ntohs(*(int16_t *)
                    (string->data + string->offset)));
#else
        obj = PyInt_FromLong((int16_t)ntohs(*(int16_t *)
                    (string->data + string->offset)));
#endif
        string->offset += 2;
        break;
    case TYPE_INT:
        HAS_SPACE(string, 4);
#ifdef IS_PYTHON3
        obj = PyLong_FromLong((int32_t)ntohl(*(int32_t *)
                    (string->data + string->offset)));
#else
        obj = PyInt_FromLong((int32_t)ntohl(*(int32_t *)
                    (string->data + string->offset)));
#endif
        string->offset += 4;
        break;
    case TYPE_LONG:
        HAS_SPACE(string, 8);
        obj = PyLong_FromLongLong(ntohll(*(int64_t *)
                    (string->data + string->offset)));
        string->offset += 8;
        break;
    case TYPE_HUGE:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        HAS_SPACE(string, size);
        obj = _PyLong_FromByteArray((unsigned char *)
                (string->data + string->offset), size, 0, 1);
        string->offset += size;
        break;
    case TYPE_DOUBLE:
        HAS_SPACE(string, 8);
        ll = ntohll(*(uint64_t *)(string->data + string->offset));
        obj = PyFloat_FromDouble(*(double *)&ll);
        string->offset += 8;
        break;
    case TYPE_SHORTSTR:
        HAS_SPACE(string, 1);
        size = *(uint8_t *)(string->data + string->offset++);
        HAS_SPACE(string, size);
#ifdef IS_PYTHON3
        obj = PyBytes_FromStringAndSize(
                string->data + string->offset, size);
#else
        obj = PyString_FromStringAndSize(
                string->data + string->offset, size);
        if (intern) PyString_InternInPlace(&obj);
#endif
        string->offset += size;
        break;
    case TYPE_LONGSTR:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        HAS_SPACE(string, size);
#ifdef IS_PYTHON3
        obj = PyBytes_FromStringAndSize(
                string->data + string->offset, size);
#else
        obj = PyString_FromStringAndSize(
                string->data + string->offset, size);
#endif
        string->offset += size;
        break;
    case TYPE_SHORTUTF8:
        HAS_SPACE(string, 1);
        size = *(uint8_t *)(string->data + string->offset++);
        HAS_SPACE(string, size);
        obj = PyUnicode_DecodeUTF8(
                string->data + string->offset, size, "strict");
        string->offset += size;
        break;
    case TYPE_LONGUTF8:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        HAS_SPACE(string, size);
        obj = PyUnicode_DecodeUTF8(
                string->data + string->offset, size, "strict");
        string->offset += size;
        break;
    case TYPE_SHORTLIST:
        HAS_SPACE(string, 1);
        size = *(char *)(string->data + string->offset++);
        obj = PyList_New(size);
        for (i = 0; i < size; i++) {
            value = load_one(string, 0);
            if (value == NULL) BREAKOUT(obj);
            PyList_SET_ITEM(obj, i, value);
        }
        break;
    case TYPE_LIST:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        obj = PyList_New(size);
        for (i = 0; i < size; i++) {
            value = load_one(string, 0);
            if (value == NULL) BREAKOUT(obj);
            PyList_SET_ITEM(obj, i, value);
        }
        break;
    case TYPE_SHORTTUPLE:
        HAS_SPACE(string, 1);
        size = *(char *)(string->data + string->offset++);
        obj = PyTuple_New(size);
        for (i = 0; i < size; i++) {
            value = load_one(string, 0);
            if (value == NULL) BREAKOUT(obj);
            PyTuple_SET_ITEM(obj, i, value);
        }
        break;
    case TYPE_TUPLE:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        obj = PyTuple_New(size);
        for (i = 0; i < size; i++) {
            value = load_one(string, 0);
            if (value == NULL) BREAKOUT(obj);
            PyTuple_SET_ITEM(obj, i, value);
        }
        break;
    case TYPE_SHORTSET:
        HAS_SPACE(string, 1);
        size = *(char *)(string->data + string->offset++);
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
        obj = PySet_Type.tp_alloc(&PySet_Type, 0);
        ((PySetObject *)obj)->data = PyDict_New();
#else
        obj = PySet_New(NULL);
#endif
        for (i = 0; i < size; i++) {
            value = load_one(string, 1);
            if (value == NULL) BREAKOUT(obj)
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
            PyDict_SetItem(((PySetObject *)obj)->data, value, Py_True);
#else
            PySet_Add(obj, value);
#endif
        }
        break;
    case TYPE_SET:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
        obj = PySet_Type.tp_alloc(&PySet_Type, 0);
        ((PySetObject *)obj)->data = PyDict_New();
#else
        obj = PySet_New(NULL);
#endif
        for (i = 0; i < size; i++) {
            value = load_one(string, 1);
            if (value == NULL) BREAKOUT(obj)
#if PY_MAJOR_VERSION == 2 && PY_MINOR_VERSION <= 4
            PyDict_SetItem(((PySetObject *)obj)->data, value, Py_True);
#else
            PySet_Add(obj, value);
#endif
        }
        break;
    case TYPE_SHORTDICT:
        HAS_SPACE(string, 1);
        size = *(char *)(string->data + string->offset++);
        obj = PyDict_New();
        while (size) {
            key = load_one(string, 1);
            if (key == NULL) BREAKOUT(obj);
            value = load_one(string, 0);
            if (value == NULL) {
                Py_XDECREF(key);
                BREAKOUT(obj);
            }
            PyDict_SetItem(obj, key, value);
            Py_XDECREF(key);
            Py_XDECREF(value);
            size--;
        }
        break;
    case TYPE_DICT:
        HAS_SPACE(string, 4);
        size = ntohl(*(uint32_t *)(string->data + string->offset));
        string->offset += 4;
        obj = PyDict_New();
        while (size) {
            key = load_one(string, 1);
            if (key == NULL) BREAKOUT(obj);
            value = load_one(string, 0);
            if (value == NULL) {
                Py_XDECREF(key);
                BREAKOUT(obj);
            }
            PyDict_SetItem(obj, key, value);
            Py_XDECREF(key);
            Py_XDECREF(value);
            size--;
        }
        break;
    default:
        PyErr_SetString(PyExc_ValueError, "invalid mummy (bad type)");
    }
    return obj;
}


static char *dumps_kwargs[] = {"object", "default", "compress", NULL};

static PyObject *
python_dumps(PyObject *self, PyObject *args, PyObject *kwargs) {
    offsetstring string;
    PyObject *obj,
             *result,
             *default_handler = Py_None,
             *compress = Py_True;
    char *cdata;
    unsigned int csize;
    int max_size;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|OO", dumps_kwargs,
            &obj, &default_handler, &compress))
        return NULL;

    string.length = INITIAL_BUFFER_SIZE;
    string.data = (char *)malloc(string.length);
    if (string.data == NULL) {
        PyErr_SetString(PyExc_MemoryError, "out of memory");
        return NULL;
    }
    string.offset = 0;

    Py_XINCREF(obj);
    Py_XINCREF(default_handler);

    if (dump_one(obj, &string, default_handler, 1))
        result = NULL;
    else {
        if (PyObject_IsTrue(compress)) {
            /* LZF Compression
             *
             * we compress everything after the first byte (the type),
             * and the final result is
             *  <type byte> | 0x80, followed by
             *  4 byte big-endian uncompressed length, followed by
             *  compressed data
             *
             *  because of these 4 bytes that wouldn't be there otherwise, the
             *  lzf compression has to beat the uncompressed version by 5 bytes
             */
            cdata = (char *)malloc(string.offset - 1);
            if (cdata == NULL) {
                free(string.data);
                PyErr_SetString(PyExc_MemoryError, "out of memory");
                return NULL;
            }

            max_size = string.offset - 6;
            max_size = max_size > 0 ? max_size : 0;
            if (max_size && (csize = lzf_compress(string.data + 1,
                    string.offset - 1, cdata + 5, string.offset - 6))) {

                cdata[0] = string.data[0] | 0x80;
                *(uint32_t *)(cdata + 1) = htonl(string.offset - 1);

                free(string.data);

                string.data = cdata;
                string.offset = string.length = csize + 5;
            }
            else free(cdata);
        }
#ifdef IS_PYTHON3
        result = PyBytes_FromStringAndSize(string.data, string.offset);
#else
        result = PyString_FromStringAndSize(string.data, string.offset);
#endif
    }

    Py_XDECREF(obj);
    Py_XDECREF(default_handler);
    free(string.data);

    return result;
}


static PyObject *
python_loads(PyObject *self, PyObject *args) {
    PyObject *data, *result;
    offsetstring string;
    unsigned int ucsize;
    char *ucdata = NULL;

#ifdef IS_PYTHON3
    if (!PyArg_ParseTuple(args, "O!", &PyBytes_Type, &data)) return NULL;
    string.data = PyBytes_AS_STRING(data);
    string.length = PyBytes_GET_SIZE(data);
#else
    if (!PyArg_ParseTuple(args, "O!", &PyString_Type, &data)) return NULL;
    string.data = PyString_AS_STRING(data);
    string.length = PyString_GET_SIZE(data);
#endif
    string.offset = 0;

    if (string.data[0] >> 7) {
        ucsize = ntohl(*(uint32_t *)(string.data + 1));

        ucdata = (char *)malloc(ucsize + 2);
        if (ucdata == NULL) {
            PyErr_SetString(PyExc_MemoryError, "out of memory");
            return NULL;
        }
        ucdata[0] = string.data[0] & 0x7f;
        ucsize = lzf_decompress(string.data + 5, string.length - 5,
                ucdata + 1, ucsize + 1);

        if (!ucsize) {
            free(ucdata);
            PyErr_SetString(PyExc_ValueError, "lzf decompression failed");
            return NULL;
        }

        string.data = ucdata;
        string.length = ucsize + 1;
    }

    result = load_one(&string, 0);

    if (ucdata) free(ucdata);

    return result;
}


static PyMethodDef methods[] = {
    {"dumps", (PyCFunction)python_dumps, METH_VARARGS | METH_KEYWORDS,
        "serialize a native python object into an mummy string"},
    {"loads", python_loads, METH_VARARGS,
        "convert an mummy string into the python object it represents"},
    {NULL, NULL, 0, NULL}
};


#ifdef IS_PYTHON3
static struct PyModuleDef _mummymodule = {
    PyModuleDef_HEAD_INIT,
    "_mummy",
    "",
    -1,
    methods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC
PyInit__mummy(void) {
    PyObject *module = PyModule_Create(&_mummymodule);
    return module;
}
#else
PyMODINIT_FUNC
init_mummy(void) {
    Py_InitModule("_mummy", methods);
}
#endif
