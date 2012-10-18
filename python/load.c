#include "mummypy.h"

extern PyDateTime_CAPI *PyDateTimeCAPI;
extern PyObject *PyDecimalType;

#define INVALID do {\
                    PyErr_SetString(PyExc_ValueError,\
                            "invalid mummy (incorrect length)");\
                    return NULL;\
                } while(0)


static PyObject *
load_one(mummy_string *str) {
    int64_t int_result = 0;
    int i, microsecond;
    int days, seconds, microseconds;
    short year, expo;
    char month, day, hour, minute, second, sign;
    uint16_t count;
    double float_result;
    PyObject *result, *key, *value, *triple;
    char *chr_ptr, *buf, flags;

    if (str->len - str->offset <= 0) {
        INVALID;
    }

    switch(mummy_type(str)) {
    case MUMMY_TYPE_NULL:
        str->offset++;
        result = Py_None;
        goto incref;

    case MUMMY_TYPE_BOOL:
        if (mummy_read_bool(str, (char *)&int_result)) INVALID;
        result = int_result ? Py_True : Py_False;
        goto incref;

    case MUMMY_TYPE_CHAR:
    case MUMMY_TYPE_SHORT:
    case MUMMY_TYPE_INT:
        if (mummy_read_int(str, &int_result)) INVALID;
        result = PyInt_FromLong(int_result);
        goto done;

    case MUMMY_TYPE_LONG:
        if (mummy_read_int(str, &int_result)) INVALID;
        result = PyLong_FromLongLong(int_result);
        goto done;

    case MUMMY_TYPE_HUGE:
        if (mummy_point_to_huge(str, &buf, (int *)&int_result)) INVALID;
        result = _PyLong_FromByteArray((unsigned char *)buf, int_result, 0, 1);
        goto done;

    case MUMMY_TYPE_FLOAT:
        if (mummy_read_float(str, &float_result)) INVALID;
        result = PyFloat_FromDouble(float_result);
        goto done;

    case MUMMY_TYPE_SHORTSTR:
    case MUMMY_TYPE_MEDSTR:
    case MUMMY_TYPE_LONGSTR:
        if (mummy_point_to_string(str, &chr_ptr, (int *)&int_result)) INVALID;
        result = PyString_FromStringAndSize(chr_ptr, int_result);
        goto done;

    case MUMMY_TYPE_SHORTUTF8:
    case MUMMY_TYPE_MEDUTF8:
    case MUMMY_TYPE_LONGUTF8:
        if (mummy_point_to_utf8(str, &chr_ptr, (int *)&int_result)) INVALID;
        result = PyUnicode_FromStringAndSize(chr_ptr, int_result);
        goto done;

    case MUMMY_TYPE_SHORTLIST:
    case MUMMY_TYPE_MEDLIST:
    case MUMMY_TYPE_LONGLIST:
        if (mummy_container_size(str, (uint32_t *)&int_result)) INVALID;
        if (NULL == (result = PyList_New((int)int_result))) goto done;
        for (i = 0; i < int_result; ++i) {
            if (NULL == (value = load_one(str))) goto fail;
            PyList_SET_ITEM(result, i, value);
        }
        goto done;

    case MUMMY_TYPE_SHORTTUPLE:
    case MUMMY_TYPE_MEDTUPLE:
    case MUMMY_TYPE_LONGTUPLE:
        if (mummy_container_size(str, (uint32_t *)&int_result)) INVALID;
        if (NULL == (result = PyTuple_New(int_result))) goto done;
        for (i = 0; i < int_result; ++i) {
            if (NULL == (value = load_one(str))) goto fail;
            PyTuple_SET_ITEM(result, i, value);
        }
        goto done;

    case MUMMY_TYPE_SHORTSET:
    case MUMMY_TYPE_MEDSET:
    case MUMMY_TYPE_LONGSET:
        if (mummy_container_size(str, (uint32_t *)&int_result)) INVALID;
        if (NULL == (result = PySet_New(NULL))) goto done;
        for (i = 0; i < int_result; ++i) {
            if (NULL == (value = load_one(str))) goto fail;
            if (PySet_Add(result, value)) {
                Py_DECREF(value);
                goto fail;
            }
        }
        goto done;

    case MUMMY_TYPE_SHORTHASH:
    case MUMMY_TYPE_MEDHASH:
    case MUMMY_TYPE_LONGHASH:
        if (mummy_container_size(str, (uint32_t *)&int_result)) INVALID;
        if (NULL == (result = PyDict_New())) goto done;
        for (i = 0; i < int_result; ++i) {
            if (NULL == (key = load_one(str))) goto fail;
            if (NULL == (value = load_one(str))) {
                Py_DECREF(key);
                goto fail;
            }
            if (PyDict_SetItem(result, key, value)) {
                Py_DECREF(key);
                Py_DECREF(value);
                goto fail;
            }
        }
        goto done;

    case MUMMY_TYPE_DATE: if (mummy_read_date(str, &year, &month, &day)) INVALID;
        result = PyDateTimeCAPI->Date_FromDate(
                year, month, day, PyDateTimeCAPI->DateType);
        goto done;

    case MUMMY_TYPE_TIME:
        if (mummy_read_time(str, &hour, &minute, &second, &microsecond))
            INVALID;
        result = PyDateTimeCAPI->Time_FromTime((int)hour, (int)minute,
                (int)second, microsecond, Py_None, PyDateTimeCAPI->TimeType);
        goto done;

    case MUMMY_TYPE_DATETIME:
        if (mummy_read_datetime(str, &year, &month, &day,
                    &hour, &minute, &second, &microsecond))
            INVALID;
        result = PyDateTimeCAPI->DateTime_FromDateAndTime(year, month, day,
                hour, minute, second, microsecond, Py_None,
                PyDateTimeCAPI->DateTimeType);
        goto done;

    case MUMMY_TYPE_TIMEDELTA:
        if (mummy_read_timedelta(str, &days, &seconds, &microseconds)) INVALID;
        result = PyDateTimeCAPI->Delta_FromDelta(days, seconds, microseconds, 1,
                PyDateTimeCAPI->DeltaType);
        goto done;

    case MUMMY_TYPE_DECIMAL:
        if (mummy_read_decimal(str, &sign, &expo, &count, &buf)) INVALID;
        if (NULL == (triple = PyTuple_New(3))) {
            free(buf);
            return NULL;
        }

        if (NULL == (value = PyTuple_New(count))) {
            free(buf);
            Py_DECREF(triple);
            return NULL;
        }
        for (i = 0; i < count; ++i) {
            if (NULL == (key = PyInt_FromLong((long)buf[i]))) {
                free(buf);
                Py_DECREF(value);
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(value, i, key);
        }
        free(buf);
        PyTuple_SET_ITEM(triple, 1, value);

        if (NULL == (value = PyInt_FromLong((long)sign))) {
            Py_DECREF(triple);
            return NULL;
        }
        PyTuple_SET_ITEM(triple, 0, value);

        if (NULL == (value = PyInt_FromLong((long)expo))) {
            Py_DECREF(triple);
            return NULL;
        }
        PyTuple_SET_ITEM(triple, 2, value);

        goto finish_decimal;
    case MUMMY_TYPE_SPECIALNUM:
        if (mummy_read_specialnum(str, &flags)) INVALID;
        if (NULL == (triple = PyTuple_New(3))) return NULL;
        switch (flags & 0xf0) {
        case MUMMY_SPECIAL_INFINITY:
            if (NULL == (value = PyInt_FromLong(flags & 0x01))) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 0, value);

            if (NULL == (value = PyTuple_New(0))) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 1, value);

            if (NULL == (value = PyString_FromString("F"))) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 2, value);

            goto finish_decimal;
        case MUMMY_SPECIAL_NAN:
            /* python's decimal module actually differentiates {s,}NaN signs,
               so it has NaN, sNaN, -NaN and -sNaN, but that's nonsense that
               mummy doesn't support (I suspect its accidental in python) */
            if (NULL == (value = PyInt_FromLong(0))) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 0, value);

            if (NULL == (value = PyTuple_New(0))) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 1, value);

            /* low byte of flags indicates NaN(0) or sNaN(1) */
            value = PyString_FromString((flags & 0x01) ? "N" : "n");
            if (NULL == value) {
                Py_DECREF(triple);
                return NULL;
            }
            PyTuple_SET_ITEM(triple, 2, value);

            goto finish_decimal;
        default:
            PyErr_SetString(PyExc_ValueError,
                    "invalid mummy (unrecognized specialnum type)");
            return NULL;
        }

    default:
        PyErr_SetString(PyExc_ValueError, "invalid mummy (unrecognized type)");
        return NULL;

    }/* switch mummy_type */

finish_decimal:
    if (NULL == (value = PyTuple_New(1))) {
        Py_DECREF(triple);
        return NULL;
    }
    PyTuple_SET_ITEM(value, 0, triple);
    result = PyObject_Call(PyDecimalType, value, NULL);
    Py_DECREF(value);
    return result;

incref:
    Py_INCREF(result);
done:
    return result;
fail:
    Py_DECREF(result);
    return NULL;
}

PyObject *
python_loads(PyObject *self, PyObject *data) {
    PyObject *result;
    mummy_string *str;
    char err, free_buf = 0;

    if (!PyBytes_CheckExact(data)) {
        PyErr_SetString(PyExc_TypeError, "argument 1 must be bytes");
        return NULL;
    }

    str = mummy_string_wrap(PyBytes_AS_STRING(data), PyBytes_GET_SIZE(data));

    /* don't have mummy_string_decompress free the buffer,
       but have it tell us whether we should or not */
    if ((err = mummy_string_decompress(str, 0, &free_buf))) {
        PyErr_Format(PyExc_ValueError, "lzf decompression failed (%d)", err);
        mummy_string_free(str, free_buf);
        return NULL;
    }

    result = load_one(str);
    mummy_string_free(str, free_buf);

    return result;
}
