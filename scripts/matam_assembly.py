#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import subprocess
import time
import logging


# Create logger
logger = logging.getLogger(__name__)

# Get program filename
program_filename = os.path.basename(sys.argv[0])

# Get MATAM root dir absolute path
matam_assembly_bin = os.path.realpath(sys.argv[0])
matam_bin_dir = os.path.dirname(matam_assembly_bin)
matam_root_dir = os.path.dirname(matam_bin_dir)
matam_db_dir = os.path.join(matam_root_dir, 'db')

# Set default ref db
default_ref_db = os.path.join(matam_db_dir, 'SILVA_123_SSURef_rdNs_NR95')

# Get all dependencies bin
matam_script_dir = os.path.join(matam_root_dir, 'scripts')
clean_name_bin = os.path.join(matam_script_dir, 'fasta_clean_name.py')
filter_score_bin = os.path.join(matam_script_dir, 'filter_score_multialign.py')
compute_lca_bin = os.path.join(matam_script_dir, 'compute_lca_from_tab.py')
compute_compressed_graph_stats_bin = os.path.join(matam_script_dir, 'compute_compressed_graph_stats.py')

sortmerna_bin_dir = os.path.join(matam_root_dir, 'sortmerna')
sortmerna_bin = os.path.join(sortmerna_bin_dir, 'sortmerna')
indexdb_bin = os.path.join(sortmerna_bin_dir, 'indexdb_rna')

ovgraphbuild_bin_dir = os.path.join(matam_root_dir, 'ovgraphbuild', 'bin')
ovgraphbuild_bin = os.path.join(ovgraphbuild_bin_dir, 'ovgraphbuild')

componentsearch_bin_dir = os.path.join(matam_root_dir, 'componentsearch')
componentsearch_jar = os.path.join(componentsearch_bin_dir, 'ComponentSearch.jar')

# Define a null file handle
FNULL = open(os.devnull, 'w')


class DefaultHelpParser(argparse.ArgumentParser):
    """
    This is a slightly modified argparse parser to display the full help
    on parser error instead of only usage
    """
    def error(self, message):
        sys.stderr.write('\nError: %s\n\n' % message)
        self.print_help()
        sys.exit(2)


def parse_arguments():
    """
    Parse the command line, and check if arguments are correct
    """
    # Initiate argument parser
    parser = DefaultHelpParser(description='MATAM assembly',
                               # to precisely format help display
                               formatter_class=lambda prog: argparse.HelpFormatter(prog, width=120, max_help_position=80))

    # Main parameters
    group_main = parser.add_argument_group('Main parameters')
    # -i / --input_fastx
    group_main.add_argument('-i', '--input_fastx',
                            action = 'store',
                            metavar = 'FASTX',
                            type = str,
                            required = True,
                            help = 'Input reads file (fasta or fastq format)')
    # -d / --ref_db
    group_main.add_argument('-d', '--ref_db',
                            action = 'store',
                            metavar = 'DBPATH',
                            type = str,
                            help = 'MATAM ref db. '
                                   'Default is $MATAM_DIR/db/SILVA_123_SSURef_rdNs_NR95')
    # -o / --out_dir
    group_main.add_argument('-o', '--out_dir',
                            action = 'store',
                            metavar = 'OUTDIR',
                            type = str,
                            help = 'Output directory.'
                                   'Default will be "matam_assembly"')
    # -v / --verbose
    group_main.add_argument('-v', '--verbose',
                            action = 'store_true',
                            help = 'Increase verbosity')

    # Performance parameters
    group_perf = parser.add_argument_group('Performance')
    # --cpu
    group_perf.add_argument('--cpu',
                            action = 'store',
                            metavar = 'CPU',
                            type = int,
                            default = 1,
                            help = 'Max number of CPU to use. '
                                   'Default is %(default)s cpu')
    # --max_memory
    group_perf.add_argument('--max_memory',
                            action = 'store',
                            metavar = 'MAXMEM',
                            type = int,
                            default = 4000,
                            help = 'Maximum memory to use (in MBi). '
                                   'Default is %(default)s MBi')

    # Reads mapping parameters
    group_mapping = parser.add_argument_group('Read mapping')
    # --best
    group_mapping.add_argument('--best',
                               action = 'store',
                               metavar = 'INT',
                               type = int,
                               default = 10,
                               help = 'Get up to --best good alignments per read. '
                                      'Default is %(default)s')
    # --min_lis
    group_mapping.add_argument('--min_lis',
                               action = 'store',
                               metavar = 'INT',
                               type = int,
                               default = 10,
                               help = argparse.SUPPRESS)
    # --evalue
    group_mapping.add_argument('--evalue',
                               action = 'store',
                               metavar = 'REAL',
                               type = float,
                               default = 1e-5,
                               help = 'Max e-value to keep an alignment for. '
                                      'Default is %(default)s')

    # Alignment filtering parameters
    group_filt = parser.add_argument_group('Alignment filtering')
    # --score_threshold
    group_filt.add_argument('--score_threshold',
                            action = 'store',
                            metavar = 'REAL',
                            type = float,
                            default = 0.9,
                            help = 'Score threshold (real between 0 and 1). '
                                   'Default is %(default)s')
    # --straight_mode
    group_filt.add_argument('--straight_mode',
                            action = 'store_true',
                            help = 'Use straight mode filtering. '
                                   'Default is geometric mode')

    # Overlap-graph building parameters
    group_ovg = parser.add_argument_group('Overlap-graph building')
    # --min_identity
    group_ovg.add_argument('--min_identity',
                           action = 'store',
                           metavar = 'REAL',
                           type = float,
                           default = 1.0,
                           help = 'Minimum identity of an overlap between 2 reads. '
                                  'Default is %(default)s')
    # --min_overlap_length
    group_ovg.add_argument('--min_overlap_length',
                           action = 'store',
                           metavar = 'INT',
                           type = int,
                           default = 50,
                           help = 'Minimum length of an overlap. '
                                  'Default is %(default)s')

    # Graph compaction & Components identification
    group_gcomp = parser.add_argument_group('Graph compaction & Components identification')
    # -N / --min_read_node
    group_gcomp.add_argument('-N', '--min_read_node',
                             action = 'store',
                             metavar = 'INT',
                             type = int,
                             default = 2,
                             help = 'Minimum number of read to keep a node. '
                                    'Default is %(default)s')
    # -E / --min_overlap_edge
    group_gcomp.add_argument('-E', '--min_overlap_edge',
                             action = 'store',
                             metavar = 'INT',
                             type = int,
                             default = 10,
                             help = 'Minimum number of overlap to keep an edge. '
                                    'Default is %(default)s')

    # LCA labelling
    group_lca = parser.add_argument_group('LCA labelling')
    # --quorum
    group_lca.add_argument('--quorum',
                           action = 'store',
                           metavar = 'FLOAT',
                           type = float,
                           default = 0.51,
                           help = 'Quorum for LCA computing. Has to be between 0.51 and 1. '
                                  'Default is %(default)s')

    # Contigs assembly

    # Scaffolding

    # Visualization

    # Advanced parameters
    group_adv = parser.add_argument_group('Advanced parameters')
    # --keep_tmp
    group_adv.add_argument('--keep_tmp',
                            action = 'store_true',
                            help = 'Do not remove tmp files')
    # --true_references
    # Fasta sequences of the known true references
    group_adv.add_argument('--true_references',
                           action = 'store',
                           type = str,
                           help = argparse.SUPPRESS)
    # --true_ref_taxo
    # Taxonomies of the true ref (represented by a 3 character id)
    # This is only needed when using a simulated dataset
    group_adv.add_argument('--true_ref_taxo',
                           action = 'store',
                           type = str,
                           help = argparse.SUPPRESS)
    # --debug
    group_adv.add_argument('--debug',
                            action = 'store_true',
                            help = 'Output debug infos')

    #
    args = parser.parse_args()

    # Arguments checking
    if args.score_threshold < 0 or args.score_threshold > 1:
        parser.print_help()
        raise Exception("score threshold not in range [0,1]")

    if args.min_identity < 0 or args.min_identity > 1:
        parser.print_help()
        raise Exception("min identity not in range [0,1]")

    if args.quorum < 0 or args.quorum > 1:
        parser.print_help()
        raise Exception("quorum not in range [0.51,1]")

    # Set debug parameters
    if args.debug:
        args.verbose = True
        args.keep_tmp = True

    # Set default ref db
    if not args.ref_db:
        args.ref_db = default_ref_db

    # Set default output dir
    if not args.out_dir:
        # args.out_dir = 'matam.{0}'.format(os.getpid())
        args.out_dir = 'matam_assembly'

    # Get absolute path for all arguments
    args.input_fastx = os.path.abspath(args.input_fastx)
    args.ref_db = os.path.abspath(args.ref_db)
    args.out_dir = os.path.abspath(args.out_dir)
    if args.true_references:
        args.true_references = os.path.abspath(args.true_references)
    if args.true_ref_taxo:
        args.true_ref_taxo = os.path.abspath(args.true_ref_taxo)

    #
    return args


def print_intro(args):
    """
    Print the introduction
    """

    sys.stdout.write("""
#################################
         MATAM assembly
#################################\n\n""")

    # Retrieve complete cmd line
    cmd_line = '{binpath} '.format(binpath=matam_assembly_bin)

    # Verbose
    if args.verbose:
        cmd_line += '--verbose '

    # Advanced parameters
    if args.debug:
        cmd_line += '--debug '

    if args.keep_tmp:
        cmd_line += '--keep_tmp '

    # Performance
    cmd_line += """--cpu {cpu} --max_memory {memory} \
""".format(cpu=args.cpu,
           memory=args.max_memory)

    # Read mapping
    cmd_line += '--best {0} '.format(args.best)
    cmd_line += '--evalue {0:.2e} '.format(args.evalue)

    # Alignment filtering
    cmd_line += '--score_threshold {0:.2f} '.format(args.score_threshold)
    if args.straight_mode:
        cmd_line += '--straight_mode '

    # Overlap-graph building
    cmd_line += '--min_identity {0:.2f} '.format(args.min_identity)
    cmd_line += '--min_overlap_length {0} '.format(args.min_overlap_length)

    # Graph compaction & Components identification
    cmd_line += '--min_read_node {0} '.format(args.min_read_node)
    cmd_line += '--min_overlap_edge {0} '.format(args.min_overlap_edge)

    # LCA labelling
    cmd_line += '--quorum {0:.2f} '.format(args.quorum)

    # Contigs assembly

    # Scaffolding

    # Visualization

    # Main parameters
    cmd_line += '--out_dir {0}'.format(args.out_dir)
    cmd_line += '--ref_db {0} '.format(args.ref_db)
    cmd_line += '--input_fastx {0}'.format(args.input_fastx)

    # Print cmd line
    sys.stdout.write('CMD: {0}\n\n'.format(cmd_line))

    return 0


def rm_files(filepath_list):
    """
    Try to delete all files in filepath_list
    """
    for filepath in filepath_list:
        try:
            logger.debug('rm {0}'.format(filepath))
            os.remove(filepath)
        except:
            pass


if __name__ == '__main__':

    # Arguments parsing
    args = parse_arguments()

    # Print intro infos
    print_intro(args)

    # Init error code
    error_code = 0

    # Set logging
    # create console handler
    ch = logging.StreamHandler()
    #
    if args.debug:
        logger.setLevel(logging.DEBUG)
        # create formatter for debug level
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    else:
        if args.verbose:
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)
        # create default formatter
        formatter = logging.Formatter('%(levelname)s - %(message)s')
    # add the formatter to the console handler
    ch.setFormatter(formatter)
    # add the handler to logger
    logger.addHandler(ch)

    # Init list of tmp files to delete at the end
    to_rm_filepath_list = list()

    ##############################################
    # Set all files and directories names + paths

    input_fastx_filepath = args.input_fastx
    input_fastx_filename = os.path.basename(input_fastx_filepath)
    input_fastx_basename, input_fastx_extension = os.path.splitext(input_fastx_filename)

    ref_db_basepath = args.ref_db
    ref_db_dir, ref_db_basename = os.path.split(ref_db_basepath)

    try:
        if not os.path.exists(args.out_dir):
            logger.debug('mkdir {0}'.format(args.out_dir))
            os.makedirs(args.out_dir)
    except OSError:
        logger.exception('Could not create output directory {0}'.format(args.out_dir))
        raise

    complete_ref_db_basename = ref_db_basename + '.complete'
    complete_ref_db_basepath = os.path.join(ref_db_dir, complete_ref_db_basename)
    complete_ref_db_filename = complete_ref_db_basename + '.fasta'
    complete_ref_db_filepath = os.path.join(ref_db_dir, complete_ref_db_filename)

    complete_ref_db_taxo_filename = complete_ref_db_basename + '.taxo.tab'
    complete_ref_db_taxo_filepath = os.path.join(ref_db_dir, complete_ref_db_taxo_filename)

    clustered_ref_db_basename = ref_db_basename + '.clustered'
    clustered_ref_db_basepath = os.path.join(ref_db_dir, clustered_ref_db_basename)
    clustered_ref_db_filename = clustered_ref_db_basename + '.fasta'
    clustered_ref_db_filepath = os.path.join(ref_db_dir, clustered_ref_db_filename)

    sortme_output_basename = input_fastx_basename
    sortme_output_basename += '.sortmerna_vs_' + ref_db_basename
    sortme_output_basename += '_b' + str(args.best) + '_m' + str(args.min_lis)
    sortme_output_basepath = os.path.join(args.out_dir, sortme_output_basename)

    sortme_output_fastx_filepath = sortme_output_basepath + '.' + input_fastx_extension
    sortme_output_sam_filepath = sortme_output_basepath + '.sam'

    score_threshold_int = int(args.score_threshold * 100)

    sam_filt_basename = sortme_output_basename + '.scr_filt_'
    if args.straight_mode:
        sam_filt_basename += 'str_'
    else:
        sam_filt_basename += 'geo_'
    sam_filt_basename += str(score_threshold_int) + 'pct'
    sam_filt_filename = sam_filt_basename + '.sam'
    sam_filt_filepath = os.path.join(args.out_dir, sam_filt_filename)

    min_identity_int = int(args.min_identity * 100)

    ovgraphbuild_basename = sam_filt_basename + '.ovgb_i' + str(min_identity_int)
    ovgraphbuild_basename += '_o' + str(args.min_overlap_length)
    ovgraphbuild_basepath = os.path.join(args.out_dir, ovgraphbuild_basename)

    ovgraphbuild_nodes_csv_filepath = ovgraphbuild_basepath + '.nodes.csv'
    ovgraphbuild_edges_csv_filepath = ovgraphbuild_basepath + '.edges.csv'

    componentsearch_basename = ovgraphbuild_basename + '.ctgs'
    componentsearch_basename += '_N' + str(args.min_read_node)
    componentsearch_basename += '_E' + str(args.min_overlap_edge)
    componentsearch_basepath = os.path.join(args.out_dir, componentsearch_basename)

    contracted_nodes_basepath = componentsearch_basepath + '.nodes_contracted'
    contracted_nodes_filepath = contracted_nodes_basepath + '.csv'
    contracted_edges_filepath = componentsearch_basepath + '.edges_contracted.csv'

    read_id_metanode_component_filepath = componentsearch_basepath + '.read_id_metanode_component.tab'
    complete_taxo_filepath = componentsearch_basepath + '.read_metanode_component_taxo.tab'

    quorum_int = int(args.quorum * 100)

    labelled_nodes_basename = componentsearch_basename + '.nodes_contracted'
    labelled_nodes_basename += '.component_lca' + str(quorum_int) + 'pct'

    components_lca_filename = componentsearch_basename + '.component_lca' + str(quorum_int) + 'pct.tab'
    components_lca_filepath = os.path.join(args.out_dir, components_lca_filename)

    stats_filename = componentsearch_basename + '.graph.stats'
    stats_filepath = os.path.join(args.out_dir, stats_filename)

    ###############################
    # Reads mapping against ref db

    logger.info('Reads mapping against ref db')

    cmd_line = sortmerna_bin + ' --ref ' + clustered_ref_db_filepath
    cmd_line += ',' + clustered_ref_db_basepath + ' --reads '
    cmd_line += input_fastx_filepath + ' --aligned ' + sortme_output_basepath
    #~ cmd_line += ' --fastx --sam --blast "1 cigar qcov" --log --best '
    cmd_line += ' --fastx --sam --blast "1" --log --best '
    cmd_line += str(args.best) + ' --min_lis ' + str(args.min_lis)
    cmd_line += ' -e {0:.2e}'.format(args.evalue)
    cmd_line += ' -a ' + str(args.cpu)
    if args.verbose:
        cmd_line += ' -v '

    logger.debug('CMD: {0}'.format(cmd_line))
    #~ error_code += subprocess.call(cmd_line, shell=True)
    if args.verbose:
        sys.stdout.write('\n')

    #############################
    # Alignment filtering

    logger.info('Alignment filtering')

    cmd_line = 'cat ' + sortme_output_sam_filepath
    cmd_line += ' | grep -v "^@" | sort -k 1,1V -k 12,12nr'
    cmd_line += ' | ' + filter_score_bin + ' -t ' + str(args.score_threshold)
    if not args.straight_mode:
        cmd_line += ' --geometric'
    cmd_line += ' > ' + sam_filt_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    #~ error_code += subprocess.call(cmd_line, shell=True)

    # Tag tmp files for removal
    #~ to_rm_filepath_list.append(sortme_output_sam_filepath)
    to_rm_filepath_list.append(sortme_output_basepath + '.log')
    to_rm_filepath_list.append(sortme_output_basepath + '.blast')

    #########################
    # Overlap-graph building

    logger.info('Overlap-graph building')

    cmd_line = ovgraphbuild_bin
    cmd_line += ' -i ' + str(args.min_identity)
    cmd_line += ' -m ' + str(args.min_overlap_length)
    cmd_line += ' --csv --output_basename '
    cmd_line += ovgraphbuild_basepath
    cmd_line += ' -r ' + clustered_ref_db_filepath
    cmd_line += ' -s ' + sam_filt_filepath
    if args.verbose:
        cmd_line += ' -v'
    if args.debug:
        cmd_line += ' --debug'

    logger.debug('CMD: {0}'.format(cmd_line))
    #~ error_code += subprocess.call(cmd_line, shell=True)

    # Tag tmp files for removal
    #~ to_rm_filepath_list.append(sam_filt_filepath)

    ###############################################
    # Graph compaction & Components identification

    logger.info('Graph compaction & Components identification')

    cmd_line = 'java -Xmx' + str(args.max_memory) + 'M -cp "'
    cmd_line += componentsearch_jar + '" main.Main'
    cmd_line += ' -N ' + str(args.min_read_node)
    cmd_line += ' -E ' + str(args.min_overlap_edge)
    cmd_line += ' -b ' + componentsearch_basepath
    cmd_line += ' -n ' + ovgraphbuild_nodes_csv_filepath
    cmd_line += ' -e ' + ovgraphbuild_edges_csv_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    #~ if args.verbose:
        #~ error_code += subprocess.call(cmd_line, shell=True)
    #~ else:
        #~ # Needed because ComponentSearch doesnt have a verbose option
        #~ # and output everything to stderr
        #~ error_code += subprocess.call(cmd_line, shell=True, stdout=FNULL)

    # Tag tmp files for removal
    #~ to_rm_filepath_list.append(ovgraphbuild_nodes_csv_filepath)
    #~ to_rm_filepath_list.append(ovgraphbuild_edges_csv_filepath)

    ################
    # LCA labelling

    logger.info('LCA labelling')

    # Note: some of the manipulations here are needed because ComponentSearch
    # works with read ids rather than read names. The goal of this part is to
    # regroup all the infos in one file (component, metanode, read, ref taxo)
    # in order to compute LCA at metanode or component level

    # Convert CSV component file to TAB format and sort by read id
    cmd_line = 'tail -n +2 ' + componentsearch_basepath + '.components.csv'
    cmd_line += ' | sed "s/;/\\t/g" | sort -k2,2 > '
    cmd_line += componentsearch_basepath + '.components.tab'

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Convert CSV node file to TAB format and sort by read id
    cmd_line = 'tail -n +2 ' + ovgraphbuild_nodes_csv_filepath
    cmd_line += ' | sed "s/;/\\t/g" | sort -k1,1 > '
    cmd_line += ovgraphbuild_basepath + '.nodes.tab'

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Join component and node files on read id, and sort by read name
    cmd_line = 'join -a1 -e"NULL" -o "1.2,0,2.3,2.1" -11 -22 '
    cmd_line += ovgraphbuild_basepath + '.nodes.tab '
    cmd_line += componentsearch_basepath + '.components.tab '
    cmd_line += '| sed "s/ /\\t/g" | sort -k1,1  > '
    cmd_line += read_id_metanode_component_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Join sam file with ref taxo on ref name, and join it to the
    # component-node file on read name.
    # Output is (read, metanode, component, taxo) file
    cmd_line = 'cat ' + sam_filt_filepath + ' | cut -f1,3 | sort -k2,2'
    cmd_line += ' | join -12 -21 - ' + complete_ref_db_taxo_filepath
    cmd_line += ' | sort -k2,2 | awk "{print \$2,\$3}" | sed "s/ /\\t/g" '
    cmd_line += ' | join -11 -21 ' + read_id_metanode_component_filepath
    cmd_line += ' - | sed "s/ /\\t/g" | cut -f2-5 > '
    cmd_line += complete_taxo_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Compute LCA at component level using quorum threshold
    cmd_line = 'cat ' + complete_taxo_filepath + ' | sort -k3,3 -k1,1 | '
    cmd_line += compute_lca_bin + ' -t 4 -f 3 -g 1 -m ' + str(args.quorum)
    cmd_line += ' -o ' + components_lca_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Tag tmp files for removal
    to_rm_filepath_list.append(componentsearch_basepath + '.components.tab')
    to_rm_filepath_list.append(ovgraphbuild_basepath + '.nodes.tab')
    to_rm_filepath_list.append(complete_taxo_filepath)

    ###################################
    # Computing compressed graph stats

    logger.info('Computing compressed graph stats')

    cmd_line = compute_compressed_graph_stats_bin + ' --nodes_contracted '
    cmd_line += contracted_nodes_filepath + ' --edges_contracted '
    cmd_line += contracted_edges_filepath + ' --components_lca '
    cmd_line += components_lca_filepath
    if args.true_ref_taxo:
        cmd_line += ' --species_taxo ' + args.true_ref_taxo
        cmd_line += ' --read_node_component ' + read_id_metanode_component_filepath
    cmd_line += ' -o ' + stats_filepath

    logger.debug('CMD: {0}'.format(cmd_line))
    error_code += subprocess.call(cmd_line, shell=True)

    # Tag tmp files for removal
    to_rm_filepath_list.append(read_id_metanode_component_filepath)

    ###################
    # Contigs assembly




    ###############
    # Exit program

    # Exit if everything went ok
    if not error_code:
        # Try to remove all tmp files
        # won't crash if it cannot
        if not args.keep_tmp:
            logger.info('Removing tmp files')
            rm_files(to_rm_filepath_list)
        #
        sys.stdout.write('\n{0} terminated with no error\n'.format(program_filename))
        exit(0)
    # Deal with errors
    else:
        sys.stdout.write('\n{0} terminated with some errors. '.format(program_filename))
        if args.verbose:
            sys.stdout.write('Check the log for additional infos\n')
        else:
            sys.stdout.write('Rerun the program using --verbose or --debug option\n')
        exit(1)
