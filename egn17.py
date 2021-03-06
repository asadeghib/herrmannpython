#!/usr/bin/python2.7
from __future__ import print_function
import matplotlib.pyplot as plt
import subprocess
import numpy as np
import sys, os
from scipy.io import loadmat, savemat
gcf, gca = plt.gcf, plt.gca

####################
help = """
computes eigenfunctions and phase velocity sensitivity kernels with Herrmann's codes
assumes that CPS has been installed and added to the path
input 
    mod96file       = ascii file at mod96 format (see Herrmann's documentation)
    wavetype        = R or L for Rayleigh or Love
    nmod            = mode number >= 0
    freq            = frequency (Hz) > 0
output 
    writes output in mat format to be read with matlab or scipy.io.loadmat
"""

####################
def execbash(script, tmpdir):
    proc = subprocess.Popen("/bin/bash", stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd = tmpdir)
    stdout, stderr = proc.communicate(script)
    return stdout, stderr
####################
def read_TXTout(fin):
    with open(fin, 'r') as fid:
        out = {}
        while True:
            l = fid.readline()
            if l == "": break
            l = l.split('\n')[0].strip()
            ####################
            if "Model:" in l:
                #first section in the file
                fid.readline() #skip header line like "LAYER     H(km)     Vp(km/s)     Vs(km/s)  Density     QA(inv)     QB(inv)"
                LAYER, H, Vp, Vs, Density, QA, QB = [], [], [], [], [], [], []
                while True:
                    l = fid.readline()
                    if l == "": break
                    layer, h, vp, vs, density, qa, qb = np.asarray(l.split('\n')[0].strip().split(), float)
                    for W, w in zip([LAYER, H, Vp, Vs, Density, QA, QB], [layer, h, vp, vs, density, qa, qb]):
                        W.append(w)
                    if h == 0: break
                del layer, h, vp, vs, density, qa, qb #prevent confusion with captial variables
                Z = np.concatenate(([0.], np.cumsum(H[:-1])))
                out['model'] = {"Z" : Z, "H" : H, "Vp" : Vp, "Vs" : Vs, "Rh" : Density}
            ####################
            elif "WAVE" in l and "MODE #" in l:
                #------------
                wavetype = l.split('WAVE')[0].strip()[0] #first letter R or L
                modenum  = int(l.split('#')[-1].split()[0])
                key = "%s%d" % (wavetype, modenum)
                #------------
                l = fid.readline()
                l = l.split('\n')[0].strip()
                l = l.split()
                T, C, U = np.asarray([l[2], l[5], l[8]], float)
                #------------
                l = fid.readline()
                l = l.split('\n')[0].strip()
                l = l.split()
                AR, GAMMA, ZREF = np.asarray([l[1], l[3], l[5]], float) #dont know what it is
                out[key] = {"T" : T, "C" : C, "U" : U, "AR" : AR, "GAMMA" : GAMMA, "ZREF" : ZREF}
                #------------
                l = fid.readline() #skip header line
                #------------
                if wavetype == "R":
                    UR, TR, UZ, TZ, DCDH, DCDA, DCDB, DCDR = [np.empty(len(H), float) for _ in xrange(8)]
                    for i in xrange(len(H)):
                        l = np.asarray(fid.readline().split('\n')[0].split(), float)
                        M = int(l[0])
                        for W, w in zip([UR, TR, UZ, TZ, DCDH, DCDA, DCDB, DCDR], l[1:]):
                            W[M - 1] = w
                    out[key]['UR'] = UR
                    out[key]['TR'] = TR
                    out[key]['UZ'] = UZ
                    out[key]['TZ'] = TZ
                    out[key]['DCDH'] = DCDH
                    out[key]['DCDA'] = DCDA
                    out[key]['DCDB'] = DCDB
                    out[key]['DCDR'] = DCDR
                elif wavetype == "L":
                    UT, TT, DCDH, DCDB, DCDR = [np.empty(len(H), float) for _ in xrange(5)]
                    for i in xrange(len(H)):
                        l = np.asarray(fid.readline().split('\n')[0].split(), float)
                        M = int(l[0])
                        for W, w in zip([UT, TT, DCDH, DCDB, DCDR], l[1:]):
                            W[M - 1] = w
                    out[key]['UT'] = UT
                    out[key]['TT'] = TT
                    out[key]['DCDH'] = DCDH
                    out[key]['DCDB'] = DCDB
                    out[key]['DCDR'] = DCDR
                else: raise Exception('error')
    return out
    
####################
if __name__ == "__main__":

    #------------------- read argument line 
    if len(sys.argv) != 5 or "-h" in sys.argv or "help" in sys.argv:
        print (help)
        sys.exit()
    mod96file = sys.argv[1]
    wavetype  = sys.argv[2]
    nmod      = int(sys.argv[3])
    freq      = float(sys.argv[4])
    display   = True
    nameout   = 'egn17out.mat'
    tmpdir    = "/tmp/tmpdir_egn17_%10d" % (np.random.rand() * 1.0e10)
    cleanup   = True

    #------------------- check access to CPS codes
    stdout, _ = execbash('which sdisp96', ".")
    if stdout == "":
        raise Exception('sdisp96 not found, make sure CPS is installed and added to the path')
        
    #------------------- check inputs
    assert os.path.exists(mod96file)
    assert wavetype in 'RL'
    assert nmod >= 0
    assert freq > 0.0
    while os.path.isdir(tmpdir):
        #make sure tmpdir does not exists
        tmpdir += "_%10d" % (np.random.rand() * 1.0e10)
    os.mkdir(tmpdir) #create temporary directory
    
    #------------------- write bash script   
    script = """
    #rm -f DISTFILE.dst sdisp96.??? s[l,r]egn96.??? S[L,R]DER.PLT S[R,L]DER.TXT

    cat << END > DISTFILE.dst 
    10. 0.125 256 -1.0 6.0
    END

    ln -s {mod96file} model.mod96
    
    ############################### prepare dispersion
    sprep96 -M model.mod96 -dfile DISTFILE.dst -NMOD {nmodmax} -{wavetype} -FREQ {freq}

    ############################### run dispersion
    sdisp96

    ############################### compute eigenfunctions
    s{minuswavetype}egn96 -DE 

    ############################### ouput eigenfunctions
    sdpder96 -{wavetype} -TXT  # plot and ascii output

    ############################### clean up
    #rm -f sdisp96.dat DISTFILE.dst sdisp96.??? s[l,r]egn96.??? S[L,R]DER.PLT

    """.format(mod96file = os.path.realpath(mod96file), 
               nmodmax = nmod + 1, 
               wavetype = wavetype, 
               minuswavetype = wavetype.lower(),
               freq = freq)
    script = "\n".join([_.strip() for _ in script.split('\n')]) #remove indentation from script
    #print (script)

    #------------------- execute bash commands
    stdout, stderr = execbash(script, tmpdir = tmpdir)
    expected_output = "%s/S%sDER.TXT" % (tmpdir, wavetype)
    if not os.path.exists(expected_output):
        raise Exception('output file %s not found, script failed \n%s' % (expected_output, stderr))

    #------------------- 
    out = read_TXTout(expected_output)
    if cleanup:
        #remove temporary directory
        execbash('rm -rf %s' % tmpdir, ".")

    #------------------- 
    if display:
        key = '%s%d' % (wavetype, nmod)
        if key not in out.keys():
            raise Exception('key %s not found in output file, is the frequency (%fHz) below the cut-off frequency for mode %d?' % (key, freq, nmod))

        ax1 = gcf().add_subplot(121)
        ax2 = gcf().add_subplot(122, sharey = ax1)
        ax1.invert_yaxis()
        #------------------
        z  = np.concatenate((np.repeat(out['model']["Z"], 2)[1:], [sum(out['model']["H"]) * 1.1]))
        vp = np.repeat(out['model']["Vp"], 2)
        vs = np.repeat(out['model']["Vs"], 2)
        rh = np.repeat(out['model']["Rh"], 2)
        ax1.plot(vp, z, label = "Vp")
        ax1.plot(vs, z, label = "Vs")
        ax1.plot(rh, z, label = "Rh")
        ax1.legend()
        ax1.grid(True)
        #------------------

        if wavetype == "R":
            ax2.plot(out[key]['UR'],  out['model']['Z'], label = "UR") #radial displacement
            ax2.plot(out[key]['UZ'],  out['model']['Z'], label = "UZ")
            ax2.plot(out[key]['TR'],  out['model']['Z'], label = "TR") #radial stress
            ax2.plot(out[key]['TZ'],  out['model']['Z'], label = "TZ")
        if wavetype == "L":
            ax2.plot(out[key]['UT'],  out['model']['Z'], label = "UT")
            ax2.plot(out[key]['TT'],  out['model']['Z'], label = "TT")        

        ax2.set_title("%s : T = %fs" % (key, out[key]["T"]))
        ax2.legend()
        ax1.set_ylabel('depth (km)')
        ax2.set_xlabel('eigenfunctions')
        ax2.grid(True)
        gcf().show()

        raw_input('pause')
    #------------------- 
    #write mat file
    print ("writing %s" % nameout)
    savemat(nameout, out)






