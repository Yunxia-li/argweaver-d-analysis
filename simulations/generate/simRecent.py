from __future__ import print_function
import sys
import msprime
import gzip
import math
import optparse
import random
import pandas

parser = optparse.OptionParser()
parser.add_option('-s', '--seed',
                  action="store", dest="seed",
                  help="Random number seed", default=None)
parser.add_option('-o', '--outdir',
                  action="store", dest="outdir",
                  help="Output directory", default=".")
parser.add_option('-c', '--chrom',
                  action="store", dest="chrom",
                  help="Chromosome name", default="chr")
parser.add_option("", "--afr",
                  action="store", dest="numAfrican",
                  help="Number of African haplotypes to sample", default=2, type="int")
parser.add_option("", "--eur", dest="numEuropean",
                  help="Number of European haplotypes to sample", default=2, type="int")
parser.add_option("", "--altai",
                  action="store", dest="numAltai",
                  help="Number of Altai haplotypes to sample", default=2, type="int")
parser.add_option("", "--vindija",
                  action="store", dest="numVindija",
                  help="Number of Vindija haplotypes to sample", default=2, type="int")
parser.add_option("", "--denisova",
                  action="store", dest="numDenisova",
                  help="Number of Denisova haplotypes to sample", default=2, type="int")
parser.add_option("", "--chimp",
                  action="store", dest="numChimp",
                  help="Number of Chimp haplotypes to sample", default=1, type="int")
parser.add_option("", "--recomb",
                  action="store", dest="recombRate",
                  help="Mean recombination rate", default=None, type="float")
parser.add_option("", "--chrX",
                  action="store_true", dest="chrX",
                  help="Reduce pop sizes by 3/4", default=False)
parser.add_option("", "--den-to-eur",
                  action="store_true", dest="denToEur",
                  help="Have den->eur migration when doing out-of-africa simulation",
                  default=False)
parser.add_option("", "--afr-to-nea", action="store_true", dest="afrToNea",
                  help="Have afr->nea migration at time=250kya, rate=0.05",
                  default=False)

options, args = parser.parse_args()

if options.seed != None:
    print("Setting seed to ", options.seed)
    random.seed(int(options.seed))
else:
    options.seed = random.randrange(sys.maxsize)
    print("Setting seed to ", options.seed)
    random.seed(int(options.seed))

print("Output directory = ", options.outdir)

### Global demographic parameters
# Many Afr/Eur popsizes are taken from Gutenkunst 2009 model
# Popsizes and divergence times are taken from Prufer 2017 and
# Kuhlwilm 2016. I tried to get most of them from Prufer but the population
# sizes were given in terms of very fragmented piecewise-constant values
# produced by PSMC- in these cases I used popsizes from Kuhlwilm estimated
# by GPhoCS


nsite = 2000000

# Times are provided in years, so we convert into generations.
generation_time = 29

# Initial popsizes for Africa
N_AF = 23700

# N_A is size of African population prior to T_AF
N_A = 18500
T_AF = 575e3 / generation_time

# This is size of European population at bottleneck, which occurs at time T_EU_AS
# r is growth rate after bottleneck, use to get initial European popsize N_EU
N_EU0 = 1000 * 2
T_EU_AS = 21.2e3 * 2 / generation_time
r_EU = 0.002
N_EU = N_EU0 / math.exp(-r_EU * T_EU_AS)
## TODO: check r_EU: N_EU is coming out at only 2*18618. OK checked... that is
## what the gutenkunst 2009 paper says

# N_B is size of EurAsian population prior to bottleneck
N_B = 2100

# This is EurAsian/African split time
## Note: Gutenkunst used 140kya, and this was with fast mutation rate, so
## in theory would be 280kya but that seems crazy.
T_B = 100e3 / generation_time


# Popsize of Neanderthal
N_NEA = 3400
# Popsize of Denisovan
N_DEN = 2500
# Split time between Nea/Den
T_ARC = 415e3 / generation_time
N_ARC = 7100

T_ALTVIN = 140e3 / generation_time


# Human/ archaic split time
T_HOM = 575e3 / generation_time

# Hominin/chimp split
T_CHIMP = 13e6 / generation_time

# Chimp popsize (shouldn't matter if only one sample and no migration)
N_CHIMP = 10000


# Note: migrates do not matter much for our purposes, except that we
# want to produce enough simulations of each type (no mig + each mig)
# to assess power


migRateNeaEur = 0.02
migTimeNeaEur = 50e3 / generation_time

# Assume migration from den into Europe at same rate, time
migRateDenEur = 0.02
migTimeDenEur = 50e3 / generation_time

migRateAfrNea = 0.0
migTimeAfrNea = 250e3 / generation_time

## Turn these off for now
migRateDenEur = 0.0
migRateAfrNea = 0.0

if (options.afrToNea):
    migRateAfrNea = 0.05

# Ancient sample ages
# Note that Altai age is estimated at 115 kya in Vindija paper
# Vindija age is estimated at 55 kya
neaAge = 115e3 / generation_time
vinAge = 52e3 / generation_time
denAge = 70e3 / generation_time


if options.chrX:
    N_AF = N_AF*0.75
    N_A = N_A*0.75
    N_NEA = N_NEA*0.75
    N_DEN = N_DEN*0.75
    N_ARC = N_ARC*0.75
    N_CHIMP = N_CHIMP*0.75


## "nea" represents vindija Neanderthal. Called this because for most of the
## duration of simulation it is both neas combined
## "alt" represents Altai neanderthal, which splits from main nea at 140kya
def out_of_africa():
    afr = 0
    eur = 1
    nea = 2
    alt = 3
    den = 4
    chimp = 5

   ## This file gives start times (looking backwards) of popsizes in each archaic population
    ## times are in generations, pop numbers correspond to above
    ## Note the popnums are all off by one, since we have added european population. I add
    ## one to them when they are used
    popsizes = pandas.read_table("archaic_popsizes.txt", names=["time", "popsize", "popnum"])
    if (options.chrX):
        popsizes.popsize = popsizes.popsize*0.75

        # Population IDs correspond to their indexes in the population
    # configuration array. Therefore, we have 0=YRI, 1=CEU and 2=CHB
    # initially.
    population_configurations = [
        msprime.PopulationConfiguration(
            sample_size=None, initial_size=N_AF),
        msprime.PopulationConfiguration(
            sample_size=None, initial_size=N_EU, growth_rate=r_EU),
        msprime.PopulationConfiguration(
            sample_size=None, initial_size=N_NEA),
        msprime.PopulationConfiguration(
            sample_size=None, initial_size=N_NEA),
        msprime.PopulationConfiguration(
            sample_size=None, initial_size=N_DEN),
        msprime.PopulationConfiguration(
            sample_size=None, initial_size = N_CHIMP)
    ]
    demographic_events = [

        # Stop europe growth
        msprime.PopulationParametersChange(
            time=T_EU_AS, initial_size=N_B, growth_rate=0, population_id=eur),

        # Nea into Eur migration
        msprime.MigrationRateChange(
            time=migTimeNeaEur, rate = migRateNeaEur, matrix_index=(eur, nea)),

        # Turn off nea/Den into eur migs
        msprime.MigrationRateChange(time = migTimeNeaEur + 1.0, rate=0),

        # Eur/Afr split
        msprime.MassMigration(
            time=T_B, source=eur, destination=afr, proportion=1.0),

        # Afr into Nea migration
        msprime.MigrationRateChange(time = migTimeAfrNea,
                                    rate = migRateAfrNea, matrix_index=(nea,afr)),
        msprime.MigrationRateChange(time = migTimeAfrNea + 1.0, rate=0),

        # Afr popsize change
        msprime.PopulationParametersChange(
            time=T_AF, initial_size=N_A, population_id=afr),



        # Den/Nea split
        msprime.MassMigration(
            time=T_ARC, source=den, destination=nea, proportion=1.0),

        # Arc/Hum split
        msprime.MassMigration(
            time=T_HOM, source=nea, destination=afr, proportion=1.0),

        # human/chimp split
        msprime.MassMigration(
            time=T_CHIMP, source=chimp, destination=afr, proportion=1.0)

    ]

    for i in range(len(popsizes)):
        demographic_events.append(
            msprime.PopulationParametersChange(time=popsizes.time[i],
                                               initial_size=popsizes.popsize[i],
                                               population_id=popsizes.popnum[i]+1))

    demographic_events.append(
        msprime.MassMigration(time=T_ALTVIN, source=alt, destination=nea, proportion=1.0))

    # Den into Eur migration
    if options.denToEur:
        demographic_events.append(
               msprime.MigrationRateChange(time=migTimeNeaEur,
                                           rate=migRateNeaEur, matrix_index=(eur,den)))

    demographic_events_sorted = []
    while len(demographic_events) > 0:
        smallestT = demographic_events[0].time
        smallestI = 0
        for i in range(len(demographic_events)):
            if demographic_events[i].time < smallestT:
                smallestT = demographic_events[i].time
                smallestI = i
        demographic_events_sorted.append(demographic_events[smallestI])
        demographic_events.remove(demographic_events[smallestI])
    demographic_events = demographic_events_sorted


    mignames = {"nToX":[eur, nea],
                "aToN":[nea, afr]}

    if options.denToEur:
        mignames["dToX"] = [eur,den]

    print(options.numAfrican, options.numEuropean, options.numAltai, options.numVindija, options.numDenisova, options.numChimp)

    samples = ( [ msprime.Sample(population=afr,time=0) ] * options.numAfrican +
                [ msprime.Sample(population=eur,time=0) ] * options.numEuropean +
                [ msprime.Sample(population=alt,time=neaAge) ] * options.numAltai +
                [ msprime.Sample(population=nea,time=vinAge) ] * options.numVindija +
                [ msprime.Sample(population=den,time=denAge) ] * options.numDenisova +
                [ msprime.Sample(population=chimp,time=0) ] * options.numChimp )

    return demographic_events, population_configurations, samples, mignames


def sample_rates(mu_rho, nsite):
    currpos = 0
    positions = []
    rho = []
    mu = []
    ## ensure that we don't "wrap around"; find the last index that we can start from
    last_idx = len(mu_rho)
    len_end = 0
    while (len_end < nsite):
        last_idx -= 1
        len_end += ( mu_rho.end[last_idx] - mu_rho.start[last_idx] )
    idx = random.randrange(last_idx)
    print(idx, last_idx, len_end)
    used_rates = pandas.DataFrame(columns=["chrom", "start", "end", "mu", "rho"])
    while (currpos < nsite):
        if options.recombRate != None:
            rho.append(options.recombRate)
        else:
            rho.append(mu_rho.rho[idx])
        mu.append(mu_rho.mu[idx])
        positions.append(currpos)
        df2=pandas.DataFrame([[mu_rho.chrom[idx], mu_rho.start[idx], mu_rho.end[idx],mu_rho.mu[idx], mu_rho.rho[idx]]],
                             columns=["chrom", "start","end","mu","rho"])
        used_rates = used_rates.append(df2)
        currpos += (mu_rho.end[idx] - mu_rho.start[idx])
        idx += 1
        if (idx == len(mu_rho)):
            print("Error! sample_rates should not wrap around")
            exit
    positions.append(nsite)
    rho.append(0)
    mu.append(0)
    used_rates.to_csv(options.outdir + "/used_rates.bed", sep="\t", header=False, index=False)
    return ( msprime.RecombinationMap(positions = positions, rates = mu),
             msprime.RecombinationMap(positions = positions, rates = rho) )


def write_map(ratemap, filename):
    outfile = open(options.outdir + "/" + filename, "w")
    pos = ratemap.get_positions()
    rates = ratemap.get_rates()
    maplen = len(pos)
    for i in range(maplen-1):
        outfile.write(options.chrom + "\t" + str(int(pos[i]+0.49))
                      + "\t" + str(int(pos[i+1]+0.49)) + "\t"
                      + str(rates[i]) + "\n")
    outfile.close()


def run_simulate(demographic_model, mmap, rmap):
    demographic_events, population_configurations, samples, mignames = demographic_model()

    # Use the demography debugger to print out the demographic history
    # that we have just described.
    #    dp = msprime.DemographyDebugger(
    #        Ne=N_A,
    #        population_configurations=population_configurations,
    #        samples=samples,
    #        demographic_events=demographic_events)
    #    dp.print_history()

    tree_sequence = msprime.simulate(recombination_map = rmap,
                                     demographic_events=demographic_events,
                                     population_configurations=population_configurations,
                                     samples=samples,
                                     record_migrations=True)

#    nsite = rmap.positions[-1]

    # msprime.simulate returns all migrations, but these include mass migrations
    # that are actually divergence. So get rid of these and get list only of
    # real migrations
    migrations = [];
    for mig in tree_sequence.migrations():
        isDivergence=False
        for d in demographic_events:
            if (type(d).__name__ != "MassMigration"): continue
            if (math.fabs(d.time - mig.time) < 0.5 and
                d.source == mig.source and
                d.dest == mig.dest):
                isDivergence=True
                break
        if (isDivergence): continue

        migName = None
        for m in mignames.keys():
            if (mignames[m][0] == mig.source and mignames[m][1] == mig.dest):
                migName = m
                break

        if (migName == None):
            sys.exit("Could not classify mig ", mig)

        migrations.append({"left": mig.left,
                           "right":mig.right,
                           "node": mig.node,
                           "time": mig.time,
                           "name": migName})

    for m in mignames.keys():
        outfile = open(options.outdir + "/" + m + ".txt", "w")
        currStart=-1
        currEnd=-1
        for tree in tree_sequence.trees():
            isMig=False
            for mig in migrations:
                if (mig['name'] != m): continue
                if (tree.interval[0] < mig['right'] and
                    tree.interval[1] >= mig['left']):
                    for node in tree.nodes():
                        if node == mig['node']:
                            isMig = True
                            break
            if isMig:
                if (currStart < 0): currStart = tree.interval[0]
                currEnd = tree.interval[1]
            else:
                if (currStart >= 0):
                    outfile.write(options.chrom + "\t" + str(int(currStart)) + "\t" + str(int(currEnd)) + "\n")
                    currStart = -1
        if (currStart >= 0):
            outfile.write(options.chrom + "\t" + str(int(currStart)) + "\t" + str(int(currEnd)) + "\n")


    outfile = open(options.outdir + "/trees.txt", "w")
    outfile.write("simulation by msprime\n")
    outfile.write(str(options.seed))
    outfile.write("\n\n//\n")
    roundingError = 0.0;
    totlen=0
    muIdx=0
    muPos=mmap.get_positions()
    if (muPos[muIdx] == 0):
        muIdx += 1
    lastMuPos=0
    for tree in tree_sequence.trees():
        newick = tree.newick(precision=6)
        left, right = tree.interval
        lastIdx=right
        intlen = (int(right-left+0.5))
        roundingError += right-left-intlen
        if (roundingError > 0.5):
            intlen += 1
            roundingError -=1
        elif (roundingError < -0.5 and intlen > 1):
            intlen -= 1
            roundingError += 1
        totlen += intlen
        while (muIdx < len(muPos) and muPos[muIdx] <= totlen):
            outfile.write("[{0},{1}]{2}\n".format(int(muPos[muIdx]) - lastMuPos,
                                                  mmap.get_rates()[muIdx],
                                                  newick))
            lastMuPos = int(muPos[muIdx])
            muIdx += 1
        if muIdx < len(muPos) and muPos[muIdx] != totlen:
            outfile.write("[{0},{1}]{2}\n".format(totlen - lastMuPos,
                                                  mmap.get_rates()[muIdx],
                                                  newick))
            lastMuPos = totlen
    outfile.close()

    write_map(rmap, "recomb_map.bed")
    write_map(mmap, "mu_map.bed")


mu_rho = pandas.read_table("mu_rho.bed.gz", names=["chrom", "start", "end", "mu", "rho"])
#if (options.recombRate != None):
#    mu_rho.rho[:len(mu_rho)] = options.recombRate
mmap , rmap = sample_rates(mu_rho, nsite)

print("Running out of Africa model")
run_simulate(out_of_africa, mmap, rmap)
