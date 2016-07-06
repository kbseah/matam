#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import argparse


def read_fasta_file_handle(fasta_file_handle):
    """
    Parse a fasta file and return a generator
    """
    # Variables initialization
    header = ''
    seqlines = list()
    sequence_nb = 0
    # Reading input file
    for line in fasta_file_handle:
        if line[0] == '>':
            # Yield the last read header and sequence
            if sequence_nb:
                yield (header, ''.join(seqlines))
                del seqlines[:]
            # Get header
            header = line[1:].rstrip()
            sequence_nb += 1
        else:
            # Concatenate sequence
            seqlines.append(line.strip())
    # Yield the input file last sequence
    yield (header, ''.join(seqlines))
    # Close input file
    fasta_file_handle.close()


def parse_cigar(cigar):
    """
    Parse a CIGAR string and return a list of (operation, count) tuples
    """
    cigar_tab = list()
    count_str = ''
    for c in cigar:
        if c.isdigit():
            count_str += c
        else:
            operation = c
            count = 1
            if count_str:
                count = int(count_str)
            cigar_tab.append((operation, count))
            count_str = ''
    #
    return cigar_tab


if __name__ == '__main__':

    # Arguments parsing
    parser = argparse.ArgumentParser(description='')
    # -i / --input_sam
    parser.add_argument('-i', '--input_sam',
                        metavar='INSAM',
                        type=argparse.FileType('r'),
                        required=True,
                        help='Input sam file, sorted by subject. '
                             'Only best alignments are expected.')
    # -r / --references
    parser.add_argument('-r', '--references',
                        metavar='REF',
                        type=argparse.FileType('r'),
                        required=True,
                        help='References fasta file (optional). '
                             'If used, the blast file should only '
                             'contain the best alignments')

    args = parser.parse_args()

    # Get ref seqs and initialize positions count
    ref_seq_dict = dict()
    ref_positions_count_dict = dict()
    total_ref_length = 0
    for header, seq in read_fasta_file_handle(args.references):
        seqid = header.split()[0]
        total_ref_length += len(seq)
        ref_seq_dict[seqid] = seq.upper()
        ref_positions_count_dict[seqid] = [0 for x in xrange(len(seq))]

    # Variables initialization
    previous_query_id = ''
    total_aligned_contigs_num = 0
    total_aligned_contigs_length = 0
    total_matches_num = 0
    total_mismatches_num = 0
    total_indel_num = 0
    total_overhang_num = 0

    # Reading sam file
    for tab in (l.split() for l in args.input_sam if l.strip()):
        # Parse sam tab
        query_id = tab[0]
        flag = int(tab[1])
        subject_id = tab[2]
        first_pos = int(tab[3]) # 1-based leftmost mapping position of the first matching base
        mapping_qual = int(tab[4])
        cigar = tab[5]
        rnext = tab[6]
        pnext = tab[7]
        tlen = tab[8]
        query_seq = tab[9].upper()
        qual = tab[10]

        # Compute additional variables
        # Is read reverse complemented ?
        reverse_complemented = flag & 0x10  # Bitwise AND. True if flag == 16
        subject_seq = ref_seq_dict[subject_id]
        subject_start = first_pos - 1 # 0-based
        query_length = len(query_seq)

        cigar_tab = parse_cigar(cigar)

        # Deal with soft clipping and get the query start (0-based)
        query_start = 0
        overhang_num = 0
        if cigar_tab[0][0] == 'S':
            count = cigar_tab[0][1]
            query_start += count
            overhang_num += count
            del cigar_tab[0]

        # Parse CIGAR
        query_end = query_start - 1
        subject_end = subject_start - 1
        indel_num = 0
        matches_num = 0
        mismatches_num = 0
        for operation, count in cigar_tab:
            if operation == 'M':
                # Compute the number of matches on this block
                local_matches_num = sum((query_seq[query_end + 1 + i] == subject_seq[subject_end + 1 + i] for i in xrange(0, count)))
                matches_num += local_matches_num
                mismatches_num += count - local_matches_num
                subject_end += count
                query_end += count
            elif operation == 'I':
                query_end += count
                indel_num += count
            elif operation == 'D':
                subject_end += count
                indel_num += count
            elif operation == 'S':
                overhang_num += count

        # Store metrics
        if query_id != previous_query_id:
            total_aligned_contigs_num += 1
            total_aligned_contigs_length += query_length
            total_matches_num += matches_num
            total_mismatches_num += mismatches_num
            total_indel_num += indel_num
            total_overhang_num += overhang_num

        #
        ref_positions_count = ref_positions_count_dict[subject_id]
        for i in xrange(subject_start, subject_end + 1):
            ref_positions_count[i] += 1

        # Store previous subject id and score
        previous_query_id = query_id

    # Final stats
    total_leven_distance = total_mismatches_num + total_indel_num + total_overhang_num
    errors_num_per_kbp = total_leven_distance * 1000.0 / total_aligned_contigs_length

    total_covered_positions_count = 0
    coverage_count_list = [0 for i in xrange(11)]
    for ref_id in ref_seq_dict:
        covered_positions_count = 0
        ref_positions_count = ref_positions_count_dict[ref_id]
        for pos_coverage in ref_positions_count:
            if pos_coverage > 0:
                covered_positions_count += 1
            if pos_coverage >= 10:
                coverage_count_list[10] += 1
            else:
                coverage_count_list[pos_coverage] += 1
        total_covered_positions_count += covered_positions_count

    max_coverage = 0
    percent_coverage_list = [0.0 for i in xrange(11)]
    for i in xrange(11):
        coverage_count = coverage_count_list[i]
        if coverage_count > 0:
            max_coverage = i
        coverage_percent = coverage_count * 100.0 / total_ref_length
        percent_coverage_list[i] = coverage_percent

    total_ref_coverage = total_covered_positions_count * 100.0 / total_ref_length

    # Output
    sys.stdout.write('Total aligned contigs num  = {0}\n'.format(total_aligned_contigs_num))
    sys.stdout.write('Total aligned contigs len  = {0}\n\n'.format(total_aligned_contigs_length))

    sys.stdout.write('Total ref length     = {0}\n\n'.format(total_ref_length))

    sys.stdout.write('Total matches num    = {0}\n'.format(total_matches_num))
    sys.stdout.write('Total mismatches num = {0}\n'.format(total_mismatches_num))
    sys.stdout.write('Total indel num      = {0}\n'.format(total_indel_num))
    sys.stdout.write('Total overhang num   = {0}\n\n'.format(total_overhang_num))

    sys.stdout.write('Total leven distance = {0}\n'.format(total_leven_distance))
    sys.stdout.write('Assembly error rate  = {0:.2f} errors / kbp\n\n'.format(errors_num_per_kbp))

    sys.stdout.write('Total ref coverage   = {0:.2f}%\n'.format(total_ref_coverage))
    sys.stdout.write('\tCov')
    for i in xrange(max_coverage + 1):
        sys.stdout.write('\t{0}'.format(i))
    sys.stdout.write('+\n\t%align')
    for i in xrange(max_coverage + 1):
        sys.stdout.write('\t{0:.2f}%'.format(percent_coverage_list[i]))
    sys.stdout.write('\n')