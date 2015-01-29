from __future__ import division  # py2

from datetime import datetime
from struct import pack

from numpy import append, delete, empty, iinfo

EDF_FORMAT = 'int16'  # by definition
edf_iinfo = iinfo(EDF_FORMAT)
DIGITAL_MAX = edf_iinfo.max
DIGITAL_MIN = edf_iinfo.min


class ExportEdf():
    """Export data to EDF.

    Notes
    -----
    Data is always recorded as 2 Byte int (which is 'int16').
    """
    def __init__(self):
        self.filename = None
        self.s_freq = None
        self.n_records = 0
        self.buffer = None

    def open(self, args):
        """Create a header, with predefined values."""
        start_time = datetime.now()
        chan_labels = [str(x) for x in range(args.n_chan)]  # maybe more creative?
        s_freq = args.s_freq
        subj_info = 'X X X X'
        recording_info = ('Startdate ' +
                           start_time.strftime('%d-%b-%Y') +
                           ' X X ' +
                           (args.dev + '/ai' + args.analoginput))

        self.s_freq = s_freq
        self.filename = args.edf
        self.convert = lambda x: ((x - args.minval) /
                                  (args.maxval - args.minval) *
                                  (DIGITAL_MAX - DIGITAL_MIN) + DIGITAL_MIN)
        self.buffer = empty((args.n_chan, 0), dtype=EDF_FORMAT)

        with open(self.filename, 'wb') as f:
            f.write('{:<8}'.format(0).encode('ascii'))
            f.write('{:<80}'.format(subj_info).encode('ascii'))  # subject_id
            f.write('{:<80}'.format(recording_info).encode('ascii'))
            f.write(start_time.strftime('%d.%m.%y').encode('ascii'))
            f.write(start_time.strftime('%H.%M.%S').encode('ascii'))

            n_records = -1   # while writing
            record_length = 1

            header_n_bytes = 256 + 256 * args.n_chan
            f.write('{:<8d}'.format(header_n_bytes).encode('ascii'))
            f.write((' ' * 44).encode('ascii'))  # reserved for EDF+

            f.write('{:<8}'.format(n_records).encode('ascii'))
            f.write('{:<8d}'.format(record_length).encode('ascii'))
            f.write('{:<4}'.format(args.n_chan).encode('ascii'))

            for one_label in chan_labels:
                f.write('{:<16}'.format(one_label).encode('ascii'))  # label
            for _ in range(args.n_chan):
                f.write(('{:<80}').format('').encode('ascii'))  # tranducer
            for _ in range(args.n_chan):
                f.write('{:<8}'.format('V').encode('ascii'))  # physical_dim
            for _ in range(args.n_chan):
                f.write('{:<8}'.format(args.minval).encode('ascii'))
            for _ in range(args.n_chan):
                f.write('{:<8}'.format(args.maxval).encode('ascii'))
            for _ in range(args.n_chan):
                f.write('{:<8}'.format(DIGITAL_MIN).encode('ascii'))
            for _ in range(args.n_chan):
                f.write('{:<8}'.format(DIGITAL_MAX).encode('ascii'))
            for _ in range(args.n_chan):
                f.write('{:<80}'.format('').encode('ascii'))  # prefiltering
            for _ in range(args.n_chan):
                f.write('{:<8d}'.format(s_freq).encode('ascii'))  # n_smp in record
            for _ in range(args.n_chan):
                f.write((' ' * 32).encode('ascii'))

    def write(self, data):
        """Write data to the EDF file. We write every second (the duration
        of one records in the EDF is one second, and the number of samples in
        one record is the sampling frequency.)
        """
        dat = self.convert(data)
        dat = dat.astype(EDF_FORMAT)

        dat[dat > DIGITAL_MAX] = DIGITAL_MAX
        dat[dat < DIGITAL_MIN] = DIGITAL_MIN

        self.buffer = append(self.buffer, dat, axis=1)

        if self.buffer.shape[1] >= self.s_freq:  # what if not integer
            x = self.buffer.flatten(order='C')

            with open(self.filename, 'ab') as f:
                f.write(pack('<' + 'h' * len(x), *x))

            self.n_records += 1
            self.buffer = delete(self.buffer, range(self.buffer.shape[1]),
                                 axis=1)

    def close(self):
        """Update header with the number of records.
        """
        with open(self.filename, 'rb+') as f:
            f.seek(236)  # where n_records is
            f.write('{:<8}'.format(self.n_records).encode('ascii'))
