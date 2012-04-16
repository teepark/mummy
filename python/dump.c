#include "mummypy.h"


/* import decimal and datetime at mummy import time */
extern PyObject *PyDecimalType;
extern PyDateTime_CAPI *PyDateTimeCAPI;


static int
dump_one(PyObject *obj, mummy_string *str, PyObject *default_handler,
        int depth) {
    int i, rc = 0;
    size_t size;
    long l;
    long long ll;
    char c, *buf;
    PyObject *key, *value, *iterator, *args;
    Py_ssize_t pst;

    /* infinite recursion protection with a max depth */
    if (depth > MUMMYPY_MAX_DEPTH) {
        PyErr_SetString(PyExc_ValueError, "maximum depth exceeded");
        return -1;
    }

    if (obj == NULL) {
        PyErr_BadInternalCall();
        return -1;
    }

    if (default_handler != Py_None && !PyCallable_Check(default_handler)) {
        PyErr_SetString(PyExc_TypeError, "default must be callable or None");
        return -1;
    }

    if (obj == Py_None) {
        rc = mummy_feed_null(str);
        goto done;
    }

    if (PyBool_Check(obj)) {
        rc = mummy_feed_bool(str, obj == Py_True ? 1 : 0);
        goto done;
    }

#if !ISPY3
    if (PyInt_CheckExact(obj)) {
        rc = mummy_feed_int(str, (int64_t)PyInt_AsLongLong(obj));
        goto done;
    }
#endif

    if (PyLong_CheckExact(obj)) {
        ll = PyInt_AsLongLong(obj);
        if (ll == -1 && PyErr_Occurred()) {
            PyErr_Clear();
            size = _PyLong_NumBits(obj) + 1;
            size = (size >> 3) + (size & 0x7 ? 1 : 0);

            if (!(buf = malloc(size))) {
                PyErr_SetString(PyExc_MemoryError, "out of memory");
                return -1;
            }
            if (_PyLong_AsByteArray((PyLongObject *)obj,
                        (unsigned char *)buf, size, 0, 1)) {
                free(buf);
                return -1;
            }

            rc = mummy_feed_huge(str, buf, size);
            free(buf);
        } else {
            rc = mummy_feed_int(str, (int64_t)ll);
        }
        goto done;
    }

    if (PyFloat_CheckExact(obj)) {
        rc = mummy_feed_float(str, PyFloat_AS_DOUBLE(obj));
        goto done;
    }

    if (PyBytes_CheckExact(obj)) {
        size = PyBytes_GET_SIZE(obj);
        rc = mummy_feed_string(str, PyBytes_AS_STRING(obj), size);
        goto done;
    }

    if (PyUnicode_CheckExact(obj)) {
        obj = PyUnicode_AsUTF8String(obj);
        size = PyBytes_GET_SIZE(obj);
        rc = mummy_feed_utf8(str, PyBytes_AS_STRING(obj), size);
        goto done;
    }

    if (PyList_CheckExact(obj)) {
        pst = PyList_GET_SIZE(obj);
        if ((rc = mummy_open_list(str, pst))) {
            goto done;
        }
        if (!(iterator = PyObject_GetIter(obj))) {
            goto fail;
        }
        while ((obj = PyIter_Next(iterator))) {
            rc = dump_one(obj, str, default_handler, depth + 1);
            Py_DECREF(obj);
            if (rc) {
                Py_DECREF(iterator);
                goto fail;
            }
        }
        Py_DECREF(iterator);
        goto done;
    }

    if (PyTuple_CheckExact(obj)) {
        pst = PyTuple_GET_SIZE(obj);
        if ((rc = mummy_open_tuple(str, pst)))
            goto done;
        if (!(iterator = PyObject_GetIter(obj)))
            goto fail;
        while ((obj = PyIter_Next(iterator))) {
            rc = dump_one(obj, str, default_handler, depth + 1);
            Py_DECREF(obj);
            if (rc) {
                Py_DECREF(iterator);
                goto fail;
            }
        }
        Py_DECREF(iterator);
        goto done;
    }

    if (PyAnySet_CheckExact(obj)) {
        pst = PySet_GET_SIZE(obj);
        if ((rc = mummy_open_set(str, pst)))
            goto done;
        if (!(iterator = PyObject_GetIter(obj)))
            goto fail;
        while ((obj = PyIter_Next(iterator))) {
            rc = dump_one(obj, str, default_handler, depth + 1);
            Py_DECREF(obj);
            if (rc) {
                Py_DECREF(iterator);
                goto fail;
            }
        }
        Py_DECREF(iterator);
        goto done;
    }

    if (PyDict_CheckExact(obj)) {
        pst = PyDict_Size(obj);
        if ((rc = mummy_open_hash(str, pst)))
            goto done;
        pst = 0;
        while (PyDict_Next(obj, &pst, &key, &value)) {
            if (dump_one(key, str, default_handler, depth + 1)) goto done;
            if (dump_one(value, str, default_handler, depth + 1)) goto done;
        }
        goto done;
    }

    if (Py_TYPE(obj) == PyDateTimeCAPI->DateType) {
        buf = (char *)((PyDateTime_Date *)obj)->data;
        /* the python datetime module inexplicably swaps the year bytes */
        rc = mummy_feed_date(
                str, bswap_16(*(unsigned short *)buf), buf[2], buf[3]);
        goto done;
    }

    if (Py_TYPE(obj) == PyDateTimeCAPI->TimeType) {
        if (((PyDateTime_Time *)obj)->hastzinfo) {
            PyErr_SetString(PyExc_ValueError,
                    "can't serialize datetime objects with tzinfo");
            return -1;
        }

        buf = (char *)((PyDateTime_Time *)obj)->data;
        /* the python datetime module swaps the three microsecond bytes */
        rc = mummy_feed_time(str, *buf, buf[1], buf[2],
                bswap_32(*(int *)(buf + 3)));
        goto done;
    }

    if (Py_TYPE(obj) == PyDateTimeCAPI->DateTimeType) {
        if (((PyDateTime_DateTime *)obj)->hastzinfo) {
            PyErr_SetString(PyExc_ValueError,
                    "can't serialize datetime objects with tzinfo");
            return -1;
        }

        buf = (char *)((PyDateTime_DateTime *)obj)->data;
        /* the python datetime module inexplicably swaps the year bytes
           and the THREE microsecond bytes */
        rc = mummy_feed_datetime(str, bswap_16(*(short *)buf),
                buf[2], buf[3], buf[4], buf[5], buf[6],
                bswap_32(*(int *)(buf + 7)));
        goto done;
    }

    if (Py_TYPE(obj) == PyDateTimeCAPI->DeltaType) {
        rc = mummy_feed_timedelta(str,
                ((PyDateTime_Delta *)obj)->days,
                ((PyDateTime_Delta *)obj)->seconds,
                ((PyDateTime_Delta *)obj)->microseconds);
        goto done;
    }

    if (Py_TYPE(obj) == (PyTypeObject *)PyDecimalType) {
        /* as_tuple() returns (sign, digit, exponent) */
        if (!(obj = PyObject_CallMethod(obj, "as_tuple", NULL))) return -1;

        /* get the exponent */
        if (!(key = PyInt_FromLong(2))) goto dec_bail0;
        if (!(value = PyObject_GetItem(obj, key))) goto dec_bail1;
        Py_DECREF(key);

        /* if 'exponent' is a string/unicode, it's a special decimal value */
        if (PyUnicode_CheckExact(value)) {
            /* convert and handle it in the string section (next) */
            key = PyUnicode_AsEncodedString(value, "ascii", "strict");
            Py_DECREF(value);
            value = key;
        }
        if (PyString_CheckExact(value)) {
            c = PyString_AS_STRING(value)[0];
            Py_DECREF(value);
            switch (c) {
            case 'n':
                rc = mummy_feed_nan(str, 0);
                goto done;
            case 'N':
                rc = mummy_feed_nan(str, 1);
                goto done;
            case 'F':
                if (!(key = PyInt_FromLong(0))) goto dec_bail0;
                if (!(value = PyObject_GetItem(obj, key))) goto dec_bail1;
                Py_DECREF(key);
                rc = mummy_feed_infinity(str, (char)PyInt_AS_LONG(value));
                Py_DECREF(value);
                goto done;
            default:
                PyErr_Format(PyExc_ValueError,
                        "unrecognized exponent: %c", c);
                goto dec_bail0;
            }
        }

        /* int/long exponent, it's a regular decimal number */
        if (PyInt_CheckExact(value) || PyLong_CheckExact(value)) {
            if (PyInt_CheckExact(value)) l = PyInt_AsLong(value);
            else l = PyLong_AsLong(value);
            Py_DECREF(value);

            if (-1 == l && PyErr_Occurred()) goto dec_bail0;
            if (l < -32768 || l >= 32768) {
                PyErr_Format(PyExc_ValueError,
                        "decimal position too big: %ld", l);
                goto dec_bail0;
            }
        } else {
            PyErr_SetString(PyExc_TypeError,
                    "unrecognized decimal exponent type");
            Py_DECREF(value);
            goto dec_bail0;
        }

        /* get the sign */
        if (!(key = PyInt_FromLong(0))) goto dec_bail0;
        if (!(value = PyObject_GetItem(obj, key))) goto dec_bail1;
        Py_DECREF(key);
        if (!(PyInt_CheckExact(value) || PyLong_CheckExact(value))) {
            PyErr_SetString(PyExc_TypeError,
                    "unrecognized decimal sign type");
            Py_DECREF(value);
            goto dec_bail0;
        }
        ll = (PyInt_CheckExact(value) ? PyInt_AsLong : PyLong_AsLong)(value);
        Py_DECREF(value);
        if (ll != 0 && ll != 1) {
            PyErr_Format(PyExc_ValueError, "invalid decimal sign: %lld", ll);
            goto dec_bail0;
        }

        /* we have the exponent and sign, on to the digits */
        if (!(key = PyInt_FromLong(1))) goto dec_bail1;
        if (!(value = PyObject_GetItem(obj, key))) goto dec_bail0;
        Py_DECREF(key);
        Py_DECREF(obj);
        if (!(PyTuple_CheckExact(value))) {
            Py_DECREF(value);
            PyErr_SetString(PyExc_TypeError, "unrecognized 'digits' type");
            goto fail;
        }
        size = PyTuple_GET_SIZE(value);
        if (!(buf = malloc(size * sizeof(char)))) {
            Py_DECREF(value);
            rc = ENOMEM;
            goto done;
        }
        iterator = PyObject_GetIter(value);
        if (!iterator) {
            Py_DECREF(value);
            goto fail;
        }
        i = 0;
        while ((obj = PyIter_Next(iterator))) {
            if (!PyInt_CheckExact(obj)) {
                PyErr_SetString(PyExc_TypeError, "non-int in 'digits'");
                Py_DECREF(iterator);
                goto dec_bail0;
            }
            buf[i++] = (char)PyInt_AsLong(obj);
            Py_DECREF(obj);
        }
        Py_DECREF(iterator);
        Py_DECREF(value);

        if ((rc = mummy_feed_decimal(
                str, (char)ll, (int16_t)l, (uint16_t)size, buf))) {
            if (EINVAL == rc) {
                PyErr_SetString(PyExc_SystemError,
                        "mummy dump internal failure");
                return -1;
            }
        }
        goto done;
    }

    /* didn't find the object type */
    if (default_handler != Py_None) {
        Py_INCREF(obj);
        if (NULL == (args = PyTuple_New(1))) {
            Py_DECREF(obj);
            return -1;
        }
        PyTuple_SET_ITEM(args, 0, obj);
        if (!(obj = PyObject_Call(default_handler, args, NULL)))
            return -1;
        rc = dump_one(obj, str, Py_None, depth);
        Py_DECREF(args);
        Py_DECREF(obj);
        return rc;
    }

    PyErr_SetString(PyExc_TypeError, "type not serializable");
    return -1;

/* caution, here be raptors */
dec_bail1:
    Py_DECREF(key);
dec_bail0:
    Py_DECREF(obj);
    return -1;
done:
    if (rc == ENOMEM) {
        PyErr_SetString(PyExc_MemoryError, "out of memory");
        return -1;
    }
    return 0;
fail:
    return -1;
}

static char *dumps_kwargs[] = {"object", "default", "compress", NULL};

PyObject *
python_dumps(PyObject *self, PyObject *args, PyObject *kwargs) {
    mummy_string *str;
    PyObject *obj,
            *result,
            *default_handler = Py_None,
            *compress = Py_True;

    if (!PyArg_ParseTupleAndKeywords(
            args, kwargs, "O|OO", dumps_kwargs,
            &obj, &default_handler, &compress))
        return NULL;

    str = mummy_string_new(MUMMYPY_STARTING_BUFFER);
    if (!str) return NULL;

    Py_INCREF(obj);
    Py_INCREF(default_handler);

    if (dump_one(obj, str, default_handler, 1))
        result = NULL;
    else {
        if (PyObject_IsTrue(compress)) {
            if (mummy_string_compress(str)) {
                mummy_string_free(str, 1);
                return NULL;
            }
        }

        result = PyBytes_FromStringAndSize(str->data, str->offset);
    }

    Py_DECREF(obj);
    Py_DECREF(default_handler);
    mummy_string_free(str, 1);
    return result;
}
