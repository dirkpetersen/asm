#! /usr/bin/env python3

"""
ASM (Amazon Science Machine) is a script that launches 
Amazon EC2 instances and installs Scientific software on them
and sets good defaults for scientific computing.
"""
# internal modules
import sys, os, argparse, json, configparser, platform, subprocess
import datetime, tarfile, zipfile, textwrap, socket, json, inspect
import math, signal, shlex, time, re, traceback, operator, glob 
import shutil, tempfile, concurrent.futures
if sys.platform.startswith('linux'):
    import getpass, pwd, grp
# stuff from pypi
import requests, boto3, botocore, psutil, urllib3
# from textual import on, work
# from textual.app import App, ComposeResult
# from textual.containers import Horizontal, Vertical
# from textual.screen import ModalScreen
# from textual.widgets import Label, Input, LoadingIndicator 
# from textual.widgets import DataTable, Footer, Button 

__app__ = 'ASM, a user friendly way to use Amazon Web Services'
__version__ = '0.1.03'

def main():
        
    if args.debug:
        pass

    if len(sys.argv) == 1:        
        print(textwrap.dedent(f'''\n
            For example, use one of these commands:
              asm config 
              asm launch
              asm ssh
            '''))

    # Instantiate classes required by all functions         
    cfg = ConfigManager(args)
    aws = None
    #if not args.subcmd in ['download', 'dld']:
    aws = AWSBoto(args, cfg)
    asmc = ASM(args, cfg, aws)
        
    if args.version:
        args_version(cfg)

    # call a function for each sub command in our CLI
    if args.subcmd in ['config', 'cnf']:
        subcmd_config(args, cfg, aws)
    elif args.subcmd in ['launch', 'lau']:
        subcmd_launch(args, cfg, asmc, aws)
    # elif args.subcmd in ['download', 'dld']:
    #     subcmd_download(args, cfg, asmc, aws)
    # elif args.subcmd in ['buildstatus', 'sta']:
    #     subcmd_buildstatus(args, cfg, aws)
    elif args.subcmd in ['ssh', 'scp']: #or args.unmount:
        subcmd_ssh(args, cfg, aws)

def args_version(cfg):
    print(f'ASM version: {__version__}')
    print(f'Python version:\n{sys.version}')
    try:
        print('Rclone version:', subprocess.run([os.path.join(cfg.binfolderx, 'rclone'), '--version'], 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.split('\n')[0])
    except FileNotFoundError as e:
        print(f'Error: {e}')
        return False
    return True
    
def subcmd_config(args, cfg, aws):
    # configure user and / or team settings 
    # arguments are Class instances passed from main

    if args.test:
        # IAM
        # roles = aws.iam_list_my_roles()
        # print('iam_list_my_roles()',roles)

        print(aws._ec2_cloud_init_script())
        print('---------------------------------------------------------------')
        print(aws._ec2_user_space_script("i-schana", "dp35.aws.internetchen.de"))
        return True
    
        print(f'get_aws_account_and_user_id()', aws.get_aws_account_and_user_id())
        print(f'iam_list_external_accounts_and_roles()', aws.iam_list_external_accounts_and_roles())

        # Route53
        print("r53_get_next_nodename('ec2-user')", aws.r53_get_next_nodename('ec2-user'))
        print("r53_get_next_nodename('asm')", aws.r53_get_next_nodename('asm'))
        nodes = aws.r53_get_short_hostnames(['35.87.193.26', '54.188.2.212', '35.83.253.36', '34.213.227.239'])
        print('Short names:', nodes)
        print('First Domain:', aws.r53_get_first_domain())
        print('Default User:', aws.ec2_get_default_user('asm.aws.internetchen.de'))        
        recs = aws._r53_get_a_records('asm')
        for rec in recs:
            print('A rec:', rec)
        print("r53_get_ip('asm.aws.internetchen.de'):", aws.r53_get_ip('asm.aws.internetchen.de'))
        print("r53_get_ip('asm'):", aws.r53_get_ip('asm'))
        print("r53_get_fqdn_or_ip('asm'):", aws.r53_get_fqdn_or_ip('asm'))
        print("r53_get_fqdn_or_ip('18.246.13.66'):", aws.r53_get_fqdn_or_ip('18.246.13.66'))
        print("r53_get_short_host_or_ip('asm.aws.internetchen.de'):", aws.r53_get_short_host_or_ip('asm.aws.internetchen.de'))
        print("r53_get_short_host_or_ip('18.246.13.66'):", aws.r53_get_short_host_or_ip('18.246.13.66'))
    
    if args.dnscleanup:
        aws.r53_cleanup(aws.hostbasename)
        return True

    if args.list:
        # list all folders in the archive
        # print('\nAll available EC2 instance families:')
        # print("--------------------------------------")
        # fams = aws.get_ec2_instance_families()
        # print(' '.join(fams))        
        # print("\nGPU    Instance Families")
        # print("--------------------------")
        # for c, i in aws.gpu_types.items():
        #     print(f'{c}: {i}')               
        print("\nCPU Type    Instance Families")
        print("--------------------------------")
        for c, i in aws.cpu_types.items():
            print(f'{c}: {" ".join(i)}')
        print('\nSupported OS, versions and CPU types (s3_prefixes)')
        print("--------------------------------------------------")
        prefixes = ['amzn-2023_graviton-3', 'amzn-2023_epyc-gen-4', 'amzn-2023_xeon-gen-4', 'rhel-9_xeon-gen-1', 'ubuntu-24.04_xeon-gen-1']
        print("\n".join(prefixes))
        return True
    
    first_time=True
    if not cfg.binfolder:
        cfg.binfolder = '~/.local/bin'
        cfg.binfolderx = os.path.expanduser(cfg.binfolder)
        if not os.path.exists(cfg.binfolderx):
            os.makedirs(cfg.binfolderx, mode=0o775, exist_ok=True)        
    else:        
        if cfg.binfolder.startswith(cfg.home_dir):
            cfg.binfolder = cfg.binfolder.replace(cfg.home_dir, '~')
        cfg.binfolderx = os.path.expanduser(cfg.binfolder)
        first_time=False
    cfg.write('general', 'binfolder', cfg.binfolder)

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not cfg.read('general', 'no-rclone-download'):
        rclonepath=os.path.join(cfg.binfolderx,'rclone')
        if not cfg.was_file_modified_in_last_24h(rclonepath):
            if os.path.exists(rclonepath):
                if os.path.exists(os.path.join(cfg.binfolderx,'bak.rclone')):
                    os.remove(os.path.join(cfg.binfolderx,'bak.rclone'))
                os.rename(rclonepath,os.path.join(cfg.binfolderx,'bak.rclone'))
            print(" Installing rclone ... please wait ... ", end='', flush=True)
            if platform.machine() in ['arm64', 'aarch64']:
                rclone_url = 'https://downloads.rclone.org/rclone-current-linux-arm64.zip'
            else:
                rclone_url = 'https://downloads.rclone.org/rclone-current-linux-amd64.zip'
            cfg.copy_binary_from_zip_url(rclone_url, 'rclone', 
                                '/rclone-v*/',cfg.binfolderx)
            print("Done!",flush=True)

    # general setup 
    defdom = cfg.get_domain_name()
    whoami = getpass.getuser()

    if args.monitor:
        # monitoring only setup, do not continue 
        me = os.path.join(cfg.binfolderx, cfg.scriptname)
        cfg.write('general', 'email', args.monitor)
        cfg.add_systemd_cron_job(f'{me} launch --monitor','30')
        return True
    
    print('\n*** Asking a few questions ***')
    print('*** For most you can just hit <Enter> to accept the default. ***\n')

    # set the correct permission for cfg.config_root 
    try:
        os.chmod(cfg.config_root, 0o2775)
    except:
        pass

    emailaddr = cfg.prompt('Enter your email address:',
                            f'{whoami}@{defdom}|general|email','string')
    emailstr = emailaddr.replace('@','-')
    emailstr = emailstr.replace('.','-')

    print("")

    host_base_name =  cfg.prompt('Please confirm/edit the standard hostname prefix. Use something short like your initials or first name. All machines will have a hostname with this prefix followed by a number ',
                                'asm|general|host_base_name','string')

    print("")

    # cloud setup
    bucket = cfg.prompt('Please confirm/edit S3 bucket name to be created in all used profiles.',
                        f'asm-{emailstr}|general|bucket','string')
    archiveroot = cfg.prompt('Please confirm/edit the root path inside your S3 bucket',
                                f'{host_base_name}|general|archiveroot','string')

    if not cfg.read('general', 's3_storage_class'):
        cfg.write('general', 's3_storage_class', 'INTELLIGENT_TIERING')


    cfg.create_aws_configs()

    aws_region = cfg.get_aws_region('aws')
    if not aws_region:
        aws_region = cfg.get_aws_region()

    if not aws_region:
        aws_region =  cfg.prompt('Please select AWS S3 region (e.g. us-west-2 for Oregon)',
                                aws.get_aws_regions())
        
    #aws_region =  cfg.prompt('Please confirm/edit the AWS S3 region', aws_region)
            
    #cfg.create_aws_configs(None, None, aws_region)
    print(f"\n  Verify that bucket '{bucket}' is configured ... ")
    
    allowed_aws_profiles = ['default', 'aws', 'AWS'] # for accessing glacier use one of these    
    profs = cfg.get_aws_profiles()

    for prof in profs:
        if prof in allowed_aws_profiles:
            cfg.set_aws_config(prof, 'region', aws_region)
            if prof == 'AWS' or prof == 'aws':
                cfg.write('general', 'aws_profile', prof)                    
            elif prof == 'default': 
                cfg.write('general', 'aws_profile', 'default')
            aws.create_s3_bucket(bucket, prof)
        
    print('\nDone!\n')


def subcmd_launch(args,cfg,asmc,aws):

    cfg.printdbg ("build:", args.awsprofile)
    cfg.printdbg(f'default cmdline: asm build')

    if args.monitor:
        # aws inactivity and cost monitoring
        aws.monitor_ec2()
        return True

    if args.awsprofile and args.awsprofile not in cfg.get_aws_profiles():
        print(f'Profile "{args.awsprofile}" not found.')
        return False    
        
    # GPU types trump CPU types 
    fams_c = []
    fam = ''
    if args.cputype:
        fams_c = aws.get_ec2_instance_families_from_cputype(args.cputype)
        if not fams_c:
            print(f'CPU type "{args.cputype}" not found. Run config --list to see types.')
            return False
        fam = fams_c[0]

    if args.gputype:
        fam = aws.get_ec2_instance_families_from_gputype(args.gputype)
        if not fam:
            print(f'GPU type "{args.gputype}" not found. Run config --list to see types.')
            return False
        args.cputype =  aws.get_ec2_cputype_from_instance_family(fam)

    if not args.cputype:
        print('Please specify a CPU or a GPU type. Run config --list to see types.')
        return False

    instance_type, _, _= aws._ec2_get_cheapest_spot_instance(args.cputype, args.vcpus, args.mem)
    numvcpus = aws._ec2_get_num_vcpus(instance_type)
        
    print(f'{instance_type} ({numvcpus} vcpus) is the cheapest spot instance with at least {args.vcpus} vcpus and {args.mem} GB mem')

    if not args.bootstrap:
        #if args.os == "amazon": # We will just use JuiceFS
        #    print('Amazon Linux will use JuiceFS')
        aws.ec2_deploy(args.disk, instance_type)
        return True

    os_id, version_id = cfg.get_os_release_info()
    if not os_id or not version_id:
        print('Could not determine OS release information.')
        return False        
    s3_prefix = f'{os_id}-{version_id}_{args.cputype}'
    if args.gputype:
        s3_prefix += f'_{args.gputype}'        
    print('s3_prefix:', s3_prefix)

    cfg.install_os_packages(['golang', 'pigz', 'iftop', 'iotop', 'htop', 'fuse3'])
    rclone = Rclone(args, cfg)
    print(f'Mounting rclone ":s3:{cfg.archivepath}/sources" at "{asmc.eb_root}/sources_s3" ...')
    rpid = rclone.mount(f':s3:{cfg.archivepath}/sources', f'{asmc.eb_root}/sources_s3')
    print(f'rclone mount pid: {rpid}')    
    # if not args.keeprunning:
    #     rclone.unmount(f'{asmc.eb_root}/sources_s3')
    #     if cfg.is_systemd_service_running('redis6') or cfg.is_systemd_service_running('redis'):
    #         ret=subprocess.run(f'sudo juicefs umount --flush /mnt/share', shell=True, text=True)        


    if not args.skipdownload:
        return False
    # *************************************************download ? ****************************    
    cfg.printdbg(f'default cmdline: asm download')
    if args.awsprofile and args.awsprofile not in cfg.get_aws_profiles():
        print(f'Profile "{args.awsprofile}" not found.')
        return False
    
    if not args.cputype and not args.prefix:
        print('Please specify a CPU type or a prefix. Use the config --list option to see types of cpus and prefixes')
        return False
    
    if args.prefix:
        s3_prefix = args.prefix
    else:   
        os_id, version_id = cfg.get_os_release_info()
        if not os_id or not version_id:
            print('Could not determine OS release information.')
            return False        
        s3_prefix = f'{os_id}-{version_id}_{args.cputype}'

    asmc.eb_root = args.target

    ret = asmc.test_write(asmc.eb_root)
    if ret==13 or ret == 2:       
        print(f'\nERROR: Folder "{asmc.eb_root}" must exist and you need write access to it.')
        return False
    
    # checking for rclone install
    if not shutil.which('rclone'):
        print(" Installing rclone ... please wait ... ", end='', flush=True)
        if platform.machine() in ['arm64', 'aarch64']:
            rclone_url = 'https://downloads.rclone.org/rclone-current-linux-arm64.zip'
        else:
            rclone_url = 'https://downloads.rclone.org/rclone-current-linux-amd64.zip'
        cfg.copy_binary_from_zip_url(rclone_url, 'rclone', 
                            '/rclone-v*/', os.path.expanduser('~/.local/bin'))
        print("Done!",flush=True) 
    if not shutil.which('rclone'):
        print('rclone not found, please add "~/.local/bin" to your PATH first.')
        return False

    # checking for lmod install:
    if not os.getenv('LMOD_VERSION'):
        if not os.path.exists('/usr/share/lmod/lmod/init'):
            print('\nLmod not found, please install it first:')
            print(' On Ubuntu/Debian: sudo apt install -y lmod')
            print(' On Amazon/RHEL: sudo dnf install -y Lmod')
            print('  (On RHEL first run: dnf install -y epel-release)')
        else:
            print('\nLmod found, but not active, please run this first:')
            print(f'source /usr/share/lmod/lmod/init/bash')

    # Running download
    print(f"\nDownloading packages from s3://{cfg.archivepath}/{s3_prefix} to {asmc.eb_root} ... ", flush=True)

    # mounting sources location
    if args.target == '/opt/eb': 
        rclone = Rclone(args, cfg)
        print(f'Mounting rclone ":s3:{cfg.archivepath}/sources" at "{asmc.eb_root}/sources_s3" ...')
        rpid = rclone.mount(f':s3:{cfg.archivepath}/sources', f'{asmc.eb_root}/sources_s3')
        print(f'rclone mount pid: {rpid}')    

    # download the Modules ()
    asmc.rclone_download_compare = '--size-only'
    asmc.download(f':s3:{cfg.archivepath}', asmc.eb_root, s3_prefix)

    print(f" Untarring packages ... ", flush=True)    
    #all_tars, new_tars = asmc._untar_eb_software(os.path.join(asmc.eb_root, 'software'))
    pref = f'{cfg.archiveroot}/{s3_prefix}/software'
    aws.s3_download_untar(cfg.bucket, pref, os.path.join(asmc.eb_root, 'software'),args.vcpus*50)

    print('All software was downloaded to:', asmc.eb_root)

    print('\nTo use these software modules, source .bashrc after adding MODULEPATH, e.g.: ')
    print(f'echo "export MODULEPATH=${{MODULEPATH}}:{asmc.eb_root}/modules/all" >> ~/.bashrc')
    print(f'source ~/.bashrc')
    if asmc.eb_root != '/opt/eb':
        print('\nAs you have not downloaded to the standard location, please create a symlink /opt/eb: ')
        print(f'sudo ln -s {asmc.eb_root} /opt/eb')    
    

def subcmd_ssh(args, cfg, aws):

    if args.terminate:
        aws.ec2_terminate_instance(args.terminate)
        return True

    ilist = aws.ec2_list_instances('Name', 'ASMSelfDestruct')
    shorthosts = [sublist[0] for sublist in ilist if sublist]
 
    if args.list:
        print ('Listing machines ... ', flush=True, end='')
        if shorthosts:                                
            aws.print_aligned_lists(ilist,"Running EC2 Instances:")      
        else:
            print('No running instances detected')
        return True 
           
    myhost = cfg.read('cloud', 'ec2_last_instance')
    remote_path = ''; scpmode = ''
    if args.sshargs:
        testpath = os.path.expanduser(args.sshargs[0]).replace('*', '')
        if os.path.exists(testpath) and len(args.sshargs) == 2:
            myhost = args.sshargs[1]
            if ':' in args.sshargs[1]:
                myhost, remote_path = args.sshargs[1].split(':')
                if args.subcmd == 'scp':
                    scpmode = 'upload'
        elif len(args.sshargs) <= 2:
            myhost = args.sshargs[0]
            if ':' in args.sshargs[0]:
                myhost, remote_path = args.sshargs[0].split(':')
                if args.subcmd == 'scp':
                    scpmode = 'download'
        else:
            print('The "ssh/scp" sub command supports currently 2 arguments')
            return False
        
    elif not myhost:
        print('Please specify a host name or IP address')
        return False

    # if the list of hosts is an ipaddress and myhost is fqdn this will not work
    if shorthosts: 
        if not myhost.split('.')[0] in shorthosts and not myhost in shorthosts:
            if '/' in myhost:
                print(f'{myhost} not found')
            else:    
                print(f'{myhost} is not running')
            return False
        
    sshuser = aws.ec2_get_default_user(myhost, ilist)

    # adding anoter public key to host
    if args.addkey:
        if not os.path.exists(args.addkey):
            args.addkey = os.path.join(cfg.config_root, 'cloud', args.addkey)
            if not os.path.exists(args.addkey):
                print(f'Private Key File {args.addkey} not found')
                return False
        ret = aws.ssh_add_key_to_remote_host(args.addkey, sshuser, myhost)
        return ret

    if scpmode:
        if scpmode == 'upload':
            ret=aws.ssh_upload(sshuser, myhost, args.sshargs[0], remote_path, False, False)
            #print(ret)  #stdout,ret.stderr
        elif scpmode == 'download':
            ret=aws.ssh_download(sshuser, myhost, remote_path, args.sshargs[1], False)
            #print(ret)  #stdout,ret.stderr
        return True
    
    if args.subcmd == 'ssh':
        print(f'Connecting to {myhost} ...')
        aws.ssh_execute(sshuser, myhost)
        return True
    
    print('This option is not supported.')
    
class ASM:
    def __init__(self, args, cfg, aws):
        self.args = args
        self.cfg = cfg
        self.aws = aws
        if self.args.nochecksums:
            self.rclone_download_compare = '--size-only'
            self.rclone_upload_compare = '--size-only'                
        else:
            self.rclone_download_compare = '--checksum'
            self.rclone_upload_compare = '--checksum'
        self.eb_root = '/opt/eb'
        self.copydelay = 3600 # 1 hour delay between 2 uploads or 2 downloads to save costs
                         
    def download(self, source, target, s3_prefix=None):  #, with_source=True
               
        rclone = Rclone(self.args,self.cfg)
            
        print ('  Downloading Modules ... ', flush=True)
        ret = rclone.copy(f'{source}/{s3_prefix}/modules/',
                          os.path.join(target,'modules'), '--fast-list',
                          '--links', self.rclone_download_compare
                        )
        self._transfer_status(ret)

        # sources are mounted from rclone
        #
        # 
        #     print ('  Downloading Sources ... ', flush=True)
        #     ret = rclone.copy(f'{source}/sources/',
        #                     os.path.join(target,'sources'), '--fast-list',
        #                     '--links', self.rclone_download_compare
        #                     )
        #     self._transfer_status(ret)
            
        #     self._make_files_executable(os.path.join(target,'sources','generic'))

        # we are now using s3 native for untar on-the-fly
        #
        # print ('  Downloading Software ... ', flush=True)
        # ret = rclone.copy(f'{source}/{s3_prefix}/software/',
        #                   os.path.join(target,'software'), '--fast-list',
        #                   '--links', self.rclone_download_compare, 
        #                   '--include', '*.eb.tar.gz' 
        #                 )        
        # self._transfer_status(ret)
            
        # for subsequent download comparison size is enough
        self.rclone_download_compare = '--size-only'
   
        return -1
    
    def _transfer_status(self, rclone_ret):
        self.cfg.printdbg('*** RCLONE copy ret ***:\n', rclone_ret, '\n')
        #print ('Message:', ret['msg'].replace('\n',';'))
        if not rclone_ret:
            return False
        if rclone_ret['stats']['errors'] > 0:
            print('Last Error:', rclone_ret['stats']['lastError'])
            print('Copying was not successful.')
            return False
            # lastError could contain: Object in GLACIER, restore first

        ttransfers=rclone_ret['stats']['totalTransfers']
        tbytes=rclone_ret['stats']['totalBytes']
        total=self._convert_size(tbytes)
        if self.args.debug:
            print('\n')
            print('Speed:', rclone_ret['stats']['speed'])
            print('Transfers:', rclone_ret['stats']['transfers'])
            print('Tot Transfers:', rclone_ret['stats']['totalTransfers'])
            print('Tot Bytes:', rclone_ret['stats']['totalBytes'])
            print('Tot Checks:', rclone_ret['stats']['totalChecks'])

        #   {'bytes': 0, 'checks': 0, 'deletedDirs': 0, 'deletes': 0, 'elapsedTime': 2.783003019, 
        #    'errors': 1, 'eta': None, 'fatalError': False, 'lastError': 'directory not found', 
        #    'renames': 0, 'retryError': True, 'speed': 0, 'totalBytes': 0, 'totalChecks': 0, 
        #    'totalTransfers': 0, 'transferTime': 0, 'transfers': 0}   
        # checksum

        if ttransfers:
            print(f'   Rclone copy: {ttransfers} file(s) with {total} transferred.')
        
    def _make_files_executable(self, path):
        for root, dirs, files in self.cfg._walker(path):
            for file in files:
                if not file.endswith('.tar.gz'):
                    file_path = os.path.join(root, file)
                    if not os.access(file_path, os.X_OK):
                        print(f'Making {file_path} executable')
                        os.chmod(file_path, os.stat(file_path).st_mode | 0o111)

    def test_write(self, directory):
        testpath=os.path.join(directory,'.asm.test')
        try:
            with open(testpath, "w") as f:
                f.write('just a test')
            os.remove(testpath)
            return True
        except PermissionError as e:
            if e.errno == 13:  # Check if error number is 13 (Permission denied)
                #print("Permission denied. Please ensure you have the necessary permissions to access the file or directory.")
                return 13
            else:
                print(f"An unexpected PermissionError occurred in {directory}:\n{e}")            
                return False
        except Exception as e:
            if e.errno == 2:
                #No such file or directory:
                return 2
            else:
                print(f"An unexpected error occurred in {directory}:\n{e}")
                return False

    
    def _convert_size(self, size_bytes):
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes/p, 3)
        return f"{s} {size_name[i]}"    
             

class Rclone:
    def __init__(self, args, cfg):
        self.args = args
        self.cfg = cfg
        self.rc = os.path.join(self.cfg.binfolderx,'rclone')

    # ensure that file exists or nagging /home/dp/.config/rclone/rclone.conf

    #backup: rclone --verbose --files-from tmpfile --use-json-log copy --max-depth 1 ./tests/ :s3:posix-dp/tests4/ --exclude .asm.md5sum
    #restore: rclone --verbose --use-json-log copy --max-depth 1 :s3:posix-dp/tests4/ ./tests2
    #rclone copy --verbose --use-json-log --max-depth 1  :s3:posix-dp/tests5/ ./tests5
    #rclone --use-json-log checksum md5 ./tests/.asm.md5sum :s3:posix-dp/tests2/
    # storage tier for each file 
    #rclone lsf --csv :s3:posix-dp/tests4/ --format=pT
    # list without subdir 
    #rclone lsjson --metadata --no-mimetype --no-modtime --hash :s3:posix-dp/tests4
    #rclone checksum md5 ./tests/.asm.md5sum --verbose --use-json-log :s3:posix-dp/archive/home/dp/gh/asm/tests

    def _run_rc(self, command):

        command = self._add_opt(command, '--verbose')
        command = self._add_opt(command, '--use-json-log')
        command = self._add_opt(command, '--transfers', str(self.args.vcpus*2))
        command = self._add_opt(command, '--checkers', str(self.args.vcpus*2))

        self.cfg.printdbg('Rclone command:', " ".join(command))
        try:
            ret = subprocess.run(command, capture_output=True, text=True, env=self.cfg.envrn)
            if ret.returncode != 0:
                #pass
                sys.stderr.write(f'*** Error, Rclone return code > 0:\n{ret.stderr} Command:\n{" ".join(command)}\n\n')
                # list of exit codes 
                # 0 - success
                # 1 - Syntax or usage error
                # 2 - Error not otherwise categorised
                # 3 - Directory not found
                # 4 - File not found
                # 5 - Temporary error (one that more retries might fix) (Retry errors)
                # 6 - Less serious errors (like 461 errors from dropbox) (NoRetry errors)
                # 7 - Fatal error (one that more retries won't fix, like account suspended) (Fatal errors)
                # 8 - Transfer exceeded - limit set by --max-transfer reached
                # 9 - Operation successful, but no files transferred
            
            #lines = ret.stderr.decode('utf-8').splitlines() #needed if you do not use ,text=True
            #locked_dirs = '\n'.join([l for l in lines if "Locked Dir:" in l]) 
            #print("   STDOUT:",ret.stdout)
            #print("   STDERR:",ret.stderr)
            #rclone mount --daemon
            return ret.stdout.strip(), ret.stderr.strip()

        except Exception as e:
            print (f'Rclone Error: {str(e)}')
            return None, str(e)

    def _run_bk(self, command):
        #command = self._add_opt(command, '--verbose')
        #command = self._add_opt(command, '--use-json-log')
        cmdline=" ".join(command)
        self.cfg.printdbg('Rclone command:', cmdline)
        try:
            ret = subprocess.Popen(command, preexec_fn=os.setsid, stdin=subprocess.PIPE, 
                        stdout=subprocess.PIPE, text=True, env=self.cfg.envrn)
            #_, stderr = ret.communicate(timeout=3)  # This does not work with rclone
            if ret.stderr:
                sys.stderr.write(f'*** Error in command "{cmdline}":\n {ret.stderr} ')
            return ret.pid
        except Exception as e:
            print (f'Rclone Error: {str(e)}')
            return None

    def copy(self, src, dst, *args):
        if src.startswith('/') and not os.path.exists(src):
            print(f'Rclone Info: Source folder {src} does not exist, skipping.')
            return []
        command = [self.rc, 'copy'] + list(args)
        command.append(src)  #command.append(f'{src}/')
        command.append(dst)
        out, err = self._run_rc(command)
        if out:
            print(f'rclone copy output: {out}')
        #print('ret', err)
        stats, ops = self._parse_log(err) 
        if stats:
            return stats[-1] # return the stats
        else:
            return []
    
        #b'{"level":"warning","msg":"Time may be set wrong - time from \\"posix-dp.s3.us-west-2.amazonaws.com\\" is -9m17.550965814s different from this computer","source":"fshttp/http.go:200","time":"2023-04-16T14:40:47.44907-07:00"}'    

    def checksum(self, md5file, dst, *args):
        #checksum md5 ./tests/.asm.md5sum
        command = [self.rc, 'checksum'] + list(args)
        command.append('md5')
        command.append(md5file)
        command.append(dst)
        #print("Command:", command)
        out, err = self._run_rc(command)
        if out:
            print(f'rclone checksum output: {out}')
        #print('ret', err)
        stats, ops = self._parse_log(err) 
        if stats:
            return stats[-1] # return the stats
        else:
            return []

    def mount(self, url, mountpoint, *args):
        if not shutil.which('fusermount3'):
            print('Could not find "fusermount3". Please install the "fuse3" OS package')
            return False
        if not url.endswith('/'): url+'/'
        mountpoint = mountpoint.rstrip(os.path.sep)
        command = [self.rc, 'mount'] + list(args)
        try:
            #os.chmod(mountpoint, 0o2775)
            current_permissions = os.stat(mountpoint).st_mode
            new_permissions = (current_permissions & ~0o07) | 0o05
            os.chmod(mountpoint, new_permissions) 
        except:
            pass
        command.append('--allow-non-empty')
        #command.append('--default-permissions')
        #command.append('--read-only')
        command.append('--no-checksum')
        command.append('--file-perms=0775')
        command.append('--quiet')
        command.append(url)
        command.append(mountpoint)
        pid = self._run_bk(command)
        return pid

    def unmount(self, mountpoint, wait=False):
        mountpoint = mountpoint.rstrip(os.path.sep)
        if self._is_mounted(mountpoint):
            if shutil.which('fusermount3'):
                cmd = ['fusermount3', '-u', mountpoint]
                ret = subprocess.run(cmd, capture_output=False, text=True, env=self.cfg.envrn)
            else:
                rclone_pids = self._get_pids('rclone')
                fld_pids = self._get_pids(mountpoint, True)
                common_pids = [value for value in rclone_pids if value in fld_pids]
                for pid in common_pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                        if wait:
                            _, _ = os.waitpid(int(pid), 0)
                        return True
                    except PermissionError:
                        print(f'Permission denied when trying to send signal SIGTERM to rclone process with PID {pid}.')
                    except Exception as e:
                        print(f'An unexpected error occurred when trying to send signal SIGTERM to rclone process with PID {pid}: {e}') 
        else:
            print(f'\nError: Folder {mountpoint} is currently not used as a mountpoint by rclone.')
                
    def version(self):
        command = [self.rc, 'version']
        return self._run_rc(command)

    def get_mounts(self):
        mounts = []
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                mount_point, fs_type = parts[1], parts[2]
                if fs_type.startswith('fuse.rclone'):
                    mounts.append(mount_point)
        return mounts

    def _get_pids(self, process, full=False):
        process = process.rstrip(os.path.sep)
        if full:
            command = ['pgrep', '-f', process]
        else:
            command = ['pgrep', process]
        try:
            output = subprocess.check_output(command)
            pids = [int(pid) for pid in output.decode().split('\n') if pid]
            return pids
        except subprocess.CalledProcessError:
            # No rclone processes found
            return []

    def _is_mounted(self, folder_path):
        folder_path = os.path.realpath(folder_path)  # Resolve any symbolic links
        with open('/proc/mounts', 'r') as f:
            for line in f:
                parts = line.split()
                mount_point, fs_type = parts[1], parts[2]
                if mount_point == folder_path and fs_type.startswith('fuse.rclone'):
                    return True


    def _add_opt(self, cmd, option, value=None):
        if option in cmd:
            return cmd
        cmd.append(option)
        if value:
            cmd.append(value)
        return cmd
    
    def _parse_log(self, strstderr):
        lines=strstderr.split('\n')
        data = [json.loads(line.rstrip()) for line in lines if line[0] == "{"]
        stats = []
        operations = []
        for obj in data:
            if 'accounting/stats' in obj['source']:
                stats.append(obj)
            elif 'operations/operations' in obj['source']:
                operations.append(obj)
        return stats, operations

        # stats":{"bytes":0,"checks":0,"deletedDirs":0,"deletes":0,"elapsedTime":4.121489785,"errors":12,"eta":null,"fatalError":false,
        # "lastError":"failed to open source object: Object in GLACIER, restore first: bucket=\"posix-dp\", key=\"tests4/table_example.py\"",
        # "renames":0,"retryError":true,"speed":0,"totalBytes":0,"totalChecks":0,"totalTransfers":0,"transferTime":0,"transfers":0},
        # "time":"2023-04-16T10:18:46.121921-07:00"}


class AWSBoto:
    # we write all config entries as files to '~/.config'
    # to make it easier for bash users to read entries 
    # with a simple var=$(cat ~/.config/asm/section/entry)
    # entries can be strings, lists that are written as 
    # multi-line files and dictionaries which are written to json

    def __init__(self, args, cfg):
        self.args = args
        self.cfg = cfg
        self.awsprofile = self.cfg.awsprofile
        self.scriptname = os.path.basename(__file__)
        self.hostbasename = self.cfg.read('general', 'host_base_name', 'asm')
        self.cpu_types = {
            "graviton-2": ('c6g', 'c6gd', 'c6gn', 'm6g', 'm6gd', 'r6g', 'r6gd', 't4g' ,'g5g'),
            "graviton-3": ('c7g', 'c7gd', 'c7gn', 'm7g', 'm7gd', 'r7g', 'r7gd'),
            "graviton-4": ('c8g', 'c8gd', 'c8gn', 'm8g', 'm8gd', 'r8g', 'r8gd'),
            "epyc-gen-1": ('t3a',),
            "epyc-gen-2": ('c5a', 'm5a', 'r5a', 'g4ad', 'p4', 'inf2', 'g5'),
            "epyc-gen-3": ('m6a', 'c6a', 'r6a', 'p5'),
            "epyc-gen-4": ('c7a', 'm7a', 'r7a'),
            "xeon-gen-1": ('c4', 'm4', 't2', 'r4', 'p3' ,'p2', 'f1', 'g3', 'i3en'),
            "xeon-gen-2": ('c5', 'c5n', 'm5', 'm5n', 'm5zn', 'r5', 't3', 't3n', 'dl1', 'inf1', 'g4dn', 'vt1'),
            "xeon-gen-3": ('c6i', 'c6in', 'm6i', 'm6in', 'r6i', 'r6id', 'r6idn', 'r6in', 'trn1'),
            "xeon-gen-4": ('c7i', 'm7i', 'm7i-flex', 'r7i', 'r7iz'),
            "core-i7-mac": ('mac1',)
        }

        # not used yet
        self.cpu_speed = {
            "graviton-2": 10,
            "graviton-3": 10,
            "graviton-4": 10,
            "epyc-gen-1": 50,
            "epyc-gen-2": 66,
            "epyc-gen-3": 85,
            "epyc-gen-4": 100,
            "xeon-gen-1": 10,
            "xeon-gen-2": 10,
            "xeon-gen-3": 10,
            "xeon-gen-4": 10,
            "core-i7-mac": 21
        }

        self.gpu_types = {
            "h100": 'p5',
            "a100": 'p4',
            "v100": 'p3',  
            "k80": 'p2',
            "gaudi": 'dl1',
            "trainium": 'trn1',
            "inferentia2": 'inf2',
            "inferentia1": 'inf1',
            "t4g": 'g5g',
            "a10g": 'g5',
            "t4": 'g4dn',
            "v520": 'g4ad',
            "m60": 'g3',
            "fpga": 'f1',
            "u30": 'vt1'            
        }

        try:
            import boto3
        except:
            print('Error: boto3 package not found. Install it first, please run:')
            print('python3 -m pip install --user --upgrade boto3')
            sys.exit(1)
        #print("PROFILE:", self.awsprofile)
        self.awssession = boto3.Session(profile_name=self.awsprofile) 
        self.r53 = self.awssession.client('route53')
        
    def get_ec2_instance_families_from_cputype(self, cpu_type):
        return self.cpu_types.get(cpu_type,[])

    def get_ec2_instance_families_from_gputype(self, gpu_type):
        return self.gpu_types.get(gpu_type,"")
    
    def get_ec2_cputype_from_instance_family(self, ifamily):
        for cputype, families in self.cpu_types.items():
            if ifamily in families:
                return cputype
        return ""

    def get_ec2_instance_families(self, profile=None):        
        ec2 = self.awssession.client('ec2')
        families = set()
        try:
            paginator = ec2.get_paginator('describe_instance_types')
            for page in paginator.paginate():
                for itype in page['InstanceTypes']:
                    # Extract the family (prefix before the dot) and add it to the set
                    family = itype['InstanceType'].split('.')[0]
                    families.add(family)

        except Exception as e:
            print(f"Error retrieving instance types: {e}")
            if type(e).__name__ == "TokenRetrievalError":
                print(f'Please run "aws ssh login" to refresh your AWS credentials.')
                sys.exit(1)            
            return []

        # Convert the set to a list and sort it to list families in order
        sorted_families = sorted(list(families))
        return sorted_families
    
    def get_ec2_smallest_instance_type(self, family, min_vcpu, min_memory, gpu_type=None, profile=None):
        #session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2 = self.awssession.client('ec2')

        # Initialize variables
        suitable_types = []
        try:
            paginator = ec2.get_paginator('describe_instance_types')
            for page in paginator.paginate():
                for itype in page['InstanceTypes']:
                    # Check if the instance type belongs to the specified family
                    if itype['InstanceType'].startswith(family):
                        vcpus = itype['VCpuInfo']['DefaultVCpus']
                        memory = itype['MemoryInfo']['SizeInMiB']

                        # Check if the instance meets the minimum vCPU and memory requirements
                        if vcpus >= min_vcpu and memory >= min_memory:
                            suitable_types.append(itype)

            # Sort suitable types by vCPUs and memory to try to get the smallest (and possibly cheapest) type
            suitable_types.sort(key=lambda x: (x['VCpuInfo']['DefaultVCpus'], x['MemoryInfo']['SizeInMiB']))

            # Assuming the first instance type is the cheapest based on the sorting
            if suitable_types:
                return suitable_types[0]['InstanceType']
            else:
                return "No suitable instance type found."

        except Exception as e:
            print(f"Error retrieving instance types: {e}")
            if type(e).__name__ == "TokenRetrievalError":
                print(f'Please run "aws ssh login" to refresh your AWS credentials.')
                sys.exit(1)               
            return []

    def get_aws_regions(self, profile=None, provider='AWS'):
        # returns a list of AWS regions 
        if provider == 'AWS':
            try:
                session = boto3.Session(profile_name=profile) if profile else boto3.Session()
                regions = session.get_available_regions('ec2')
                # make the list a little shorter 
                regions = [i for i in regions if not i.startswith('ap-')]
                return sorted(regions, reverse=True)
            except:
                return ['us-west-2','us-west-1', 'us-east-1', '']
            
    def get_aws_account_and_user_id(self):
        # returns aws account_id, user_id, user_name
        # Initialize the STS client
        try:
            sts_client = self.awssession.client('sts')
            # Get the caller identity
            response = sts_client.get_caller_identity()
            # Extract the account ID
            account_id = response['Account']
            user_id = response['UserId']
            # Extract the ARN and parse the user ID
            arn = response['Arn']
            user_name = arn.split(':')[-1].split('/')[-1]
            return account_id, user_id, user_name
        except Exception as e:
            print(f"Error in get_aws_account_and_user_id(): {e}")
            sys.exit(1)            

    def check_bucket_access(self, bucket_name, readwrite=False, profile=None):
        
        if not bucket_name:
            print('check_bucket_access: bucket_name empty. You may have not yet configured a S3 bucket name. Please run "asm config" first')
            sys.exit(1)    
        if not self._check_s3_credentials(profile):
            print('_check_s3_credentials failed. Please edit file ~/.aws/credentials')
            return False
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ep_url = self.cfg._get_aws_s3_session_endpoint_url(profile)
        s3 = session.client('s3', endpoint_url=ep_url)
        
        try:
            # Check if bucket exists
            s3.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '403':
                print(f"Error: Access denied to bucket {bucket_name} for profile {self.awsprofile}. Check your permissions.")
            elif error_code == '404':
                print(f"Error: Bucket {bucket_name} does not exist in profile {self.awsprofile}.")
                print("run 'asm config' to create this bucket.")
            else:
                print(f"Error accessing bucket {bucket_name} in profile {self.awsprofile}: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error in function check_bucket_access for profile {self.awsprofile}: {e}")
            return False

        if not readwrite:
            return True
        
        # Test write access by uploading a small test file
        try:
            test_object_key = "test_write_access.txt"
            s3.put_object(Bucket=bucket_name, Key=test_object_key, Body="Test write access")
            #print(f"Successfully wrote test to {bucket_name}")

            # Clean up by deleting the test object
            s3.delete_object(Bucket=bucket_name, Key=test_object_key)
            #print(f"Successfully deleted test object from {bucket_name}")
            return True
        except botocore.exceptions.ClientError as e:
            print(f"Error: cannot write to bucket {bucket_name} in profile {self.awsprofile}: {e}")
            return False
        

    def create_s3_bucket(self, bucket_name, profile=None):   
        if not self._check_s3_credentials(profile, verbose=True):
            print(f"Cannot create bucket '{bucket_name}' with these credentials")
            print('check_s3_credentials failed. Please edit file ~/.aws/credentials')
            return False 
        region = self.cfg.get_aws_region(profile)
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ep_url = self.cfg._get_aws_s3_session_endpoint_url(profile)
        s3_client = session.client('s3', endpoint_url=ep_url)        
        existing_buckets = s3_client.list_buckets()
        for bucket in existing_buckets['Buckets']:
            if bucket['Name'] == bucket_name:
                self.cfg.printdbg(f'S3 bucket {bucket_name} exists')
                return True
        try:
            if region and region != 'default-placement':
                response = s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                    )
            else:
                response = s3_client.create_bucket(
                    Bucket=bucket_name,
                    )              
            print(f"Created S3 Bucket '{bucket_name}'")
        except botocore.exceptions.BotoCoreError as e:
            print(f"BotoCoreError: {e}")
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidBucketName':
                print(f"Error: Invalid bucket name '{bucket_name}'\n{e}")
            elif error_code == 'BucketAlreadyExists':
                pass
                #print(f"Error: Bucket '{bucket_name}' already exists.")
            elif error_code == 'BucketAlreadyOwnedByYou':
                pass
                #print(f"Error: You already own a bucket named '{bucket_name}'.")
            elif error_code == 'InvalidAccessKeyId':
                #pass
                print("Error: InvalidAccessKeyId. The AWS Access Key Id you provided does not exist in our records")
            elif error_code == 'SignatureDoesNotMatch':
                pass
                #print("Error: Invalid AWS Secret Access Key.")
            elif error_code == 'AccessDenied':
                print("Error: Access denied. Check your account permissions for creating S3 buckets")
            elif error_code == 'IllegalLocationConstraintException':
                print(f"Error: The specified region '{region}' is not valid.")
            else:
                print(f"ClientError: {e}")
            return False
        except Exception as e:            
            print(f"An unexpected error occurred: {e}")
            return False
        encryption_configuration = {
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }
            ]
        }
        try:
            response = s3_client.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration=encryption_configuration
            )            
            print(f"Applied AES256 encryption to S3 bucket '{bucket_name}'")    
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidBucketName':
                print(f"Error: Invalid bucket name '{bucket_name}'\n{e}")
            elif error_code == 'AccessDenied':
                print("Error: Access denied. Check your account permissions for creating S3 buckets")
            elif error_code == 'IllegalLocationConstraintException':
                print(f"Error: The specified region '{region}' is not valid.")
            elif error_code == 'InvalidLocationConstraint':
                if not ep_url:
                    # do not show this error with non AWS endpoints 
                    print(f"Error: The specified location-constraint '{region}' is not valid")
            else:
                print(f"ClientError: {e}")                        
        except Exception as e:            
            print(f"An unexpected error occurred in create_s3_bucket: {e}")
            return False            
        return True
    
    def _check_s3_credentials(self, profile=None, verbose=False):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        try:
            if verbose or self.args.debug:
                self.cfg.printdbg(f'  Checking credentials for profile "{profile}" ... ', end='')            
            ep_url = self.cfg._get_aws_s3_session_endpoint_url(profile)
            s3_client = session.client('s3', endpoint_url=ep_url)            
            s3_client.list_buckets()
            if verbose or self.args.debug:
                pass
                #print('Done.')                
        except botocore.exceptions.NoCredentialsError:
            print("No AWS credentials found. Please check your access key and secret key.")
        except botocore.exceptions.EndpointConnectionError:
            print("Unable to connect to the AWS S3 endpoint. Please check your internet connection.")
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            #error_code = e.response['Error']['Code']             
            if error_code == 'RequestTimeTooSkewed':
                print(f"The time difference between S3 storage and your computer is too high:\n{e}")
            elif error_code == 'InvalidAccessKeyId':                
                print(f"Error: Invalid AWS Access Key ID in profile {profile}:\n{e}")
                print(f"Fix your credentials in ~/.aws/credentials for profile {profile}")
            elif error_code == 'SignatureDoesNotMatch':                
                if "Signature expired" in str(e): 
                    print(f"Error: Signature expired. The system time of your computer is likely wrong:\n{e}")
                    return False
                else:
                    print(f"Error: Invalid AWS Secret Access Key in profile {profile}:\n{e}")         
            elif error_code == 'InvalidClientTokenId':
                print(f"Error: Invalid AWS Access Key ID or Secret Access Key !")
                print(f"Fix your credentials in ~/.aws/credentials for profile {profile}")                
            else:
                print(f"Error validating credentials for profile {profile}: {e}")
                print(f"Fix your credentials in ~/.aws/credentials for profile {profile}")
            return False
        except Exception as e:
            print(f"An unexpected Error in _check_s3_credentials with profile {profile}: {e}")
            if type(e).__name__ == "TokenRetrievalError":
                print(f'Please run "aws ssh login" to refresh your AWS credentials.')        
            sys.exit(1)
        return True
    
    def s3_get_json(self, o_name):
        try:
            s3 = self.awssession.client('s3')        
            obj = s3.get_object(Bucket=self.cfg.bucket, Key=o_name, RequestPayer='requester')
            return json.loads(obj['Body'].read())
        except Exception as e:
            print(f"Error in s3_get_json accessing bucket '{self.cfg.bucket}': {e}")
            return {}
        
    def s3_put_json(self, o_name, json_data):
        try:
            s3 = self.awssession.client('s3')
            return s3.put_object(Bucket=self.cfg.bucket, Key=o_name, Body=json.dumps(json_data, indent=4), RequestPayer='requester')
        except Exception as e:
            print(f"Error in s3_put_json accessing bucket '{self.cfg.bucket}': {e}")
            return False

    def s3_duplicate_bucket(self, src_bucket, dst_bucket, max_workers=100, tier='INTELLIGENT_TIERING'):

        s3 = self.awssession.client('s3')

        def s3_copy_object(s3, src_bucket, dst_bucket, obj, tier):
            try:
                # Check if the object exists in the destination bucket
                dest_obj = s3.head_object(Bucket=dst_bucket, Key=obj['Key'], RequestPayer='requester')
                # Compare ETags (remove quotation marks from ETags if necessary)
                if dest_obj['ETag'] == obj['ETag']:
                    print(f"  Skipping {obj['Key']}, target exists.")
                    return
            except botocore.exceptions.ClientError:
                # Object does not exist in the destination bucket
                pass
            except Exception as e:
                print(f"Error 1 in s3_copy_object: {e}")
                pass

            # Copy object with Requester Pays option
            try:
                copy_source = {'Bucket': src_bucket, 'Key': obj['Key']}
                s3.copy(copy_source, dst_bucket, obj['Key'],
                    ExtraArgs={'RequestPayer': 'requester', 'StorageClass': tier})
                print(f"Copied {obj['Key']} from {src_bucket} to {dst_bucket}")
            except Exception as e:               
                print(f"Error 2 in s3_copy_object: {e}")
                pass

        try:
            paginator = s3.get_paginator('list_objects_v2')
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Iterate over each page in the paginator
                for page in paginator.paginate(Bucket=src_bucket, RequestPayer='requester'):
                    if 'Contents' in page:
                        # Submit each object copy to the thread pool
                        futures = [executor.submit(s3_copy_object, s3, src_bucket, dst_bucket, obj, tier)
                                for obj in page['Contents']] # if obj['Size'] <= 5 * 1024 * 1024 * 1024
                        # Wait for all submitted futures to complete
                        concurrent.futures.wait(futures)
        except Exception as e:
            print(f"Error in s3_duplicate_bucket(): {e}")
            return False

    def s3_download_untar(self, src_bucket, prefix, dst_root, max_workers=100):

        s3 = self.awssession.client('s3')
        if not prefix.endswith('/'):
            prefix += '/'

        def s3_untar_object(s3, src_bucket, prefix, obj, dst_root):
            try:
                if obj['Key'].endswith('.eb.tar.gz'):
                    tail = obj['Key'][len(prefix):]
                    dst_fld = os.path.dirname(os.path.join(dst_root,tail))
                    stub_file = os.path.join(dst_root,tail) + '.stub'
                    if os.path.exists(stub_file):
                        print(f"   Skiping {obj['Key']} ... already extracted")
                        return
                    else:
                        print(f"   Extr. {obj['Key']} ...")
                    if not os.path.exists(dst_fld):
                        os.makedirs(dst_fld, exist_ok=True)              
                    fobj = s3.get_object(Bucket=src_bucket, Key=obj['Key'], RequestPayer='requester')
                    stream = fobj['Body']
                    with tarfile.open(mode="r|gz", fileobj=stream._raw_stream) as tar:
                        for member in tar:
                            # Extract each member while preserving attributes
                            tar.extract(member, path=dst_fld)                
                    # Alternative method using BytesIO but consumes much more memory
                    # tar_obj = tarfile.open(fileobj=io.BytesIO(stream.read()), mode="r:gz")
                    # tar_obj.extractall(path=dst_fld)
                    #
                    # Some extracted files may have wrong permissions, fix them, add rw to owner
                    for root, dirs, files in self.cfg._walker(dst_fld):
                        for name in dirs + files:
                            full_path = os.path.join(root, name)
                            # Skip if the path is a symlink
                            if os.path.islink(full_path):
                                continue                            
                            current_permissions = os.stat(full_path).st_mode
                            # Preserve the owner's execute bit if it's set, only modify read and write bits
                            owner_execute = current_permissions & 0o100  # Owner execute bit
                            new_permissions = (current_permissions & 0o7077) | 0o600 | owner_execute
                            os.chmod(full_path, new_permissions)
                    with open(stub_file, 'w') as fil:
                        pass 
                else:
                    print(f"**** Skipping {obj['Key']}, not a tar.gz file.")

            except Exception as e:
                if "seeking backwards is not allowed" in str(e):
                    print(f"**** Skipping {obj['Key']}, overwriting not allowed")
                else:
                    print(f"Error in s3_untar_object: {e}")
                return False

        try:
            paginator = s3.get_paginator('list_objects_v2')
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:            
                # Iterate over each page in the paginator
                for page in paginator.paginate(Bucket=src_bucket, Prefix=prefix, RequestPayer='requester'):
                    if 'Contents' in page:
                        # Submit each object copy to the thread pool
                        futures = [executor.submit(s3_untar_object, s3, src_bucket, prefix, obj, dst_root)
                                for obj in page['Contents']] # if obj['Size'] <= 5 * 1024 * 1024 * 1024
                        # Wait for all submitted futures to complete
                        concurrent.futures.wait(futures)
        except Exception as e:
            print(f"Error in s3_download_untar: {e}")
            return False

    def s3_get_size_gb(self, bucket, prefix):
        try:
            s3 = self.awssession.client('s3')
            if not prefix.endswith('/'):
                prefix += '/'
            total_size_bytes = 0
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        total_size_bytes += obj['Size']
            total_size_gib = total_size_bytes / (2**30)
            return total_size_gib
        except Exception as e:
            print(f"Error in s3_get_size_gb: {e}")
            return 0

    def _extract_last_float(self, input_string):
        # Finding all occurrences of a floating-point number pattern
        matches = re.findall(r'\d+\.\d+', input_string)
        if matches:
            # Return the last match
            return float(matches[-1])
        else:
            return None

    def ec2_deploy(self, disk_gib, instance_type, awsprofile=None):

        try:
            import boto3
        except:
            print('Error: boto3 package not found. Install it first, please run:')
            print('python3 -m pip install --user --upgrade boto3')
            sys.exit(1)        

        if not awsprofile: 
            awsprofile = self.cfg.awsprofile
        prof = self._ec2_create_iam_policy_roles_ec2profile()            
        iid, fqdn, ip = self._ec2_launch_instance(disk_gib, instance_type, prof, awsprofile)
        if not iid:
            return False
        print(f' Waiting for ssh host {fqdn} to become ready ...')
        if not self.cfg.wait_for_ssh_ready(fqdn, ip):  # socket.gethostbyname(fqdn)
            return False
        bootstrap_build = self._ec2_user_space_script(iid, fqdn)        

        ### this block may need to be moved to a function
        cmdlist = [item for item in sys.argv]
        awsargs = ['--instance-type', '-t', '--az', '-z', '--on-demand', '-d'] # if found remove option and next arg        
        cmdlist = [x for i, x in enumerate(cmdlist) if x \
                   not in awsargs and (i == 0 or cmdlist[i-1] not in awsargs)]  
        if not '--profile' in cmdlist and self.args.awsprofile:
            cmdlist.insert(1,'--profile')
            cmdlist.insert(2, self.args.awsprofile)
        if not '--bootstrap' in cmdlist:
           cmdlist.append('--bootstrap')
        cmdline = self.scriptname + " " + " ".join(map(shlex.quote, cmdlist[1:])) #original cmdline
        ### end block 

        print(f" will execute '{cmdline}' on {fqdn} ... ")
        bootstrap_build += '\n$PYBIN ~/.local/bin/' + cmdline + f' >> ~/out.asm.{iid}.txt 2>&1'
        # once everything is done, commit suicide, but only if ~/no-terminate does not exist:

        sshuser = self.ec2_get_default_user(fqdn)
        ret = self.ssh_upload(sshuser, fqdn,
            bootstrap_build, "bootstrap.sh", is_string=True)        
        #if ret.stdout or ret.stderr:
            #print(ret.stdout, ret.stderr)
        ret = self.ssh_execute(sshuser, fqdn, 
            'mkdir -p ~/.config/asm/general')
        if ret.stdout or ret.stderr:
            print(ret.stdout, ret.stderr)        
        ret = self.ssh_upload(sshuser, fqdn,
            "~/.config/asm/general/*", ".config/asm/general/")
        #if ret.stdout or ret.stderr:
            #print(ret.stdout, ret.stderr)        
        ret = self.ssh_execute(sshuser, fqdn, 
            f'nohup bash bootstrap.sh < /dev/null > out.bootstrap.{iid}.txt 2>&1 &')
        if ret.stdout or ret.stderr:
            print(ret.stdout, ret.stderr)
        print(' Executed bootstrap and build script ... you may have to wait a while ...')
        print(' but you can already login using "asm ssh"')

        if os.path.exists(os.path.expanduser('~/.bash_history.tmp')):
            os.remove(os.path.expanduser('~/.bash_history.tmp'))
        qt = "'"
        os.system(f'echo "touch ~/no-terminate && pkill -f asm" >> ~/.bash_history.tmp')  
        os.system(f'echo "tail -n 30 -f ~/out.bootstrap.{iid}.txt" >> ~/.bash_history.tmp')
        ret = self.ssh_upload(sshuser, fqdn,
            "~/.bash_history.tmp", ".bash_history")
        if ret.stdout or ret.stderr:
            #print(ret.stdout, ret.stderr)
            pass

        self.send_email_ses('', '', 'ASM build on EC2', f'this command line was executed on host {fqdn}:\n{cmdline}')


    def _ec2_describe_instance_families(self, cpu_type, vcpus=1, memory_gb=1, region=None):
        # use a filter on ec2.describe_instance_types() to get a list of instance types
        ec2 = boto3.client('ec2', region_name=region) if region else self.awssession.client('ec2')

        instance_families = self.cpu_types[cpu_type]
        filtered_instance_families = []

        try:
            # Retrieve all instance types
            paginator = ec2.get_paginator('describe_instance_types')
            page_iterator = paginator.paginate()

            for page in page_iterator:
                for instance_type in page['InstanceTypes']:
                    if instance_type['InstanceType'].startswith(instance_families) and \
                    instance_type['VCpuInfo']['DefaultVCpus'] >= vcpus and \
                    instance_type['MemoryInfo']['SizeInMiB'] >= memory_gb * 1024:
                        filtered_instance_families.append(instance_type)

            #instance_ids = [i['InstanceType'] for i in filtered_instance_families]
            #print('\nfiltered_instance_families:', instance_ids)
        except Exception as e:
            print(f"Error retrieving instance types: {e}")
            if type(e).__name__ == "TokenRetrievalError":
                print(f'Please run "aws ssh login" to refresh your AWS credentials.')
                sys.exit(1)               
            return []
        
        return filtered_instance_families
    
    def _ec2_create_or_get_iam_policy(self, pol_name, pol_doc, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        iam = session.client('iam')

        policy_arn = None
        try:
            response = iam.create_policy(
                PolicyName=pol_name,
                PolicyDocument=json.dumps(pol_doc,indent=4)
            )
            policy_arn = response['Policy']['Arn']
            print(f"Policy created with ARN: {policy_arn}")
        except iam.exceptions.EntityAlreadyExistsException as e:
            policies = iam.list_policies(Scope='Local')  
               # Scope='Local' for customer-managed policies, 
               # 'AWS' for AWS-managed policies            
            for policy in policies['Policies']:
                if policy['PolicyName'] == pol_name:
                    policy_arn = policy['Arn']
                    break
            print(f'Policy {pol_name} already exists')
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
            else:
                print(f'Client Error: {e}')
        except Exception as e:
            print('Other Error:', e)
        return policy_arn

    def _ec2_create_aws_eb_iam_policy(self, profile=None):
        # Initialize session with specified profile or default
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()

        # Create IAM client
        iam = session.client('iam')

        # Define policy name and policy document
        policy_name = 'ASMEC2DescribePolicy'
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ec2:Describe*",
                    "Resource": "*"
                }
            ]
        }

        # Get current IAM user's details
        user = iam.get_user()
        user_name = user['User']['UserName']

        # Check if policy already exists for the user
        existing_policies = iam.list_user_policies(UserName=user_name)
        if policy_name in existing_policies['PolicyNames']:
            print(f"{policy_name} already exists for user {user_name}.")
            return

        # Create policy for user
        iam.put_user_policy(
            UserName=user_name,
            PolicyName=policy_name,
            PolicyDocument=json.dumps(policy_document, indent=4)
        )

        print(f"Policy {policy_name} attached successfully to user {user_name}.")


    def _ec2_create_iam_policy_roles_ec2profile(self, profile=None):
        # create all the IAM requirement to allow an ec2 instance to
        # 1. self destruct, 2. monitor cost with CE and 3. send emails via SES
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        iam = session.client('iam')

      # Step 0: Create IAM self destruct and EC2 read policy 
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "ec2:Describe*",     # Basic EC2 read permissions
                    ],
                    "Resource": "*"
                },                
                {
                    "Effect": "Allow",
                    "Action": "ec2:TerminateInstances",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "ec2:ResourceTag/Name": "ASMSelfDestruct"
                        }
                    }
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ce:GetCostAndUsage"
                    ],
                    "Resource": "*"
                }
            ]
        }
        policy_name = 'ASMSelfDestructPolicy'     

        destruct_policy_arn = self._ec2_create_or_get_iam_policy(
            policy_name, policy_document, profile)
    
        # 1. Create an IAM role
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ec2.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                },
            ]
        }

        role_name = "ASMEC2Role"
        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy, indent=4),
                Description='ASM role allows Billing, SES and Terminate'
            )
        except iam.exceptions.EntityAlreadyExistsException:        
            print (f'Role {role_name} already exists.') 
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
            else:
                print(f'Client Error: {e}')
        except Exception as e:            
            print('Other Error:', e)
        
        # 2. Attach permissions policies to the IAM role
        cost_explorer_policy = "arn:aws:iam::aws:policy/AWSBillingReadOnlyAccess"
        ses_policy = "arn:aws:iam::aws:policy/AmazonSESFullAccess"

        try:
        
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=cost_explorer_policy
            )
            
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=ses_policy
            )

            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=destruct_policy_arn
            )
        except iam.exceptions.PolicyNotAttachableException as e:
            print(f"Policy {e.policy_arn} is not attachable. Please check your permissions.")
            return False
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
            else:
                print(f'Client Error: {e}')
        except Exception as e:
            print('Other Error:', e)
            return False
        # 3. Create an instance profile and associate it with the role
        instance_profile_name = "ASMEC2Profile"
        try:
            iam.create_instance_profile(
                InstanceProfileName=instance_profile_name
            )
            iam.add_role_to_instance_profile(
                InstanceProfileName=instance_profile_name,
                RoleName=role_name
            )
        except iam.exceptions.EntityAlreadyExistsException:
            print (f'Profile {instance_profile_name} already exists.')
            return instance_profile_name
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
            else:
                print(f'Client Error: {e}')
            return None
        except Exception as e:            
            print('Other Error:', e)
            return None
        
        # Give AWS a moment to propagate the changes
        print('wait for 15 sec ...')
        time.sleep(15)  # Wait for 15 seconds

        return instance_profile_name
    
    def _ec2_create_and_attach_security_group(self, instance_id, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2 = session.resource('ec2')
        client = session.client('ec2')

        group_name = 'SSH-HTTP-ICMP'
        
        # Check if security group already exists
        security_groups = client.describe_security_groups(Filters=[{'Name': 'group-name', 'Values': [group_name]}])
        if security_groups['SecurityGroups']:
            security_group_id = security_groups['SecurityGroups'][0]['GroupId']
        else:
            # Create security group
            response = client.create_security_group(
                GroupName=group_name,
                Description='Allows SSH and ICMP inbound traffic'
            )
            security_group_id = response['GroupId']
        
            # Allow ports 22, 80, 443, 8000-9000, ICMP
            client.authorize_security_group_ingress(
                GroupId=security_group_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 80,
                        'ToPort': 80,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 443,
                        'ToPort': 443,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 8000,
                        'ToPort': 9000,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    },                    {
                        'IpProtocol': 'icmp',
                        'FromPort': -1,  # -1 allows all ICMP types
                        'ToPort': -1,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0'}]
                    }
                ]
            )
        
        # Attach the security group to the instance
        instance = ec2.Instance(instance_id)
        current_security_groups = [sg['GroupId'] for sg in instance.security_groups]
        
        # Check if the security group is already attached to the instance
        if security_group_id not in current_security_groups:
            current_security_groups.append(security_group_id)
            instance.modify_attribute(Groups=current_security_groups)

        return security_group_id

    def _ec2_get_latest_amazon_linux_ami(self, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2_client = session.client('ec2')

        myarch = 'x86_64'
        if self.args.cputype.startswith('graviton'):
            myarch = 'arm64'

        response = ec2_client.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['al202*-ami-*']},
                {'Name': 'state', 'Values': ['available']},
                {'Name': 'architecture', 'Values': [myarch]},
                {'Name': 'virtualization-type', 'Values': ['hvm']}
            ]            
            #amzn2-ami-hvm-2.0.*-x86_64-gp2
            #al2023-ami-kernel-default-x86_64
        )

        # Sort images by creation date to get the latest
        images = sorted(response['Images'], key=lambda k: k['CreationDate'], reverse=True)
        if images:
            iname = images[0]["Name"].split('/')[-1]
            print(f'Using AMI image {iname}')
            return images[0]['ImageId']
        else:
            return None       

    def _ec2_get_latest_ubuntu_lts_ami(self, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2_client = session.client('ec2')

        myarch = 'x86_64'
        if self.args.cputype.startswith('graviton'):
            myarch = 'arm64'

        response = ec2_client.describe_images(
            Owners=['099720109477'],  # Ubuntu's owner ID
            Filters=[
                {'Name': 'name', 'Values': ['ubuntu/images/hvm-*/ubuntu-*']}, # or hvm-* hvm-ssd-gp3
                {'Name': 'description', 'Values': ['*LTS*']},
                {'Name': 'architecture', 'Values': [myarch]},
                {'Name': 'virtualization-type', 'Values': ['hvm']},
                {'Name': 'state', 'Values': ['available']}
            ]
            #amzn2-ami-hvm-2.0.*-x86_64-gp2
            #al2023-ami-kernel-default-x86_64
        )

        # Sort images by creation date / Description to get the latest
        images = sorted(response['Images'], key=lambda k: k['Description'], reverse=True)  
        if images:
            iname = images[0]["Name"].split('/')[-1]
            print(f'Using AMI image {iname}')
            return images[0]['ImageId']
        else:
            return None        

    def _ec2_get_latest_rocky_linux_ami(self, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2_client = session.client('ec2')

        myarch = 'x86_64'
        if self.args.cputype.startswith('graviton'):
            myarch = 'arm64'

        response = ec2_client.describe_images(
            #Owners=['679593333241'], # Rocky's owner ID
            Owners=['792107900819'], # Rocky's owner ID            
            #Owners=['309956199498'], # RedHat's owner ID
            Filters=[
                {'Name': 'name', 'Values': ['Rocky-9-EC2-Base*','Rocky-10-EC2-Base*' ]},
                {'Name': 'architecture', 'Values': [myarch]},
                {'Name': 'virtualization-type', 'Values': ['hvm']},
                {'Name': 'state', 'Values': ['available']}
            ]            
            #amzn2-ami-hvm-2.0.*-x86_64-gp2
            #al2023-ami-kernel-default-x86_64
        )

        # Sort images by creation date to get the latest
        images = sorted(response['Images'], key=lambda k: k['DeprecationTime'], reverse=True) 
           #dateutil.parser.parse() or datetime.datetime.fromisoformat(date_string.rstrip('Z'))
        #print(images[0])
        #sys.exit(1)
        if images:
            iname = images[0]["Name"].split('/')[-1]
            print(f'Using AMI image {iname}')
            return images[0]['ImageId']
        else:
            return None 

    def _ec2_get_latest_other_linux_ami(self, osname, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2_client = session.client('ec2')

        myarch = 'x86_64'
        if self.args.cputype.startswith('graviton'):
            myarch = 'arm64'

        response = ec2_client.describe_images(
            Filters=[
                {'Name': 'name', 'Values': [osname]},
                {'Name': 'architecture', 'Values': [myarch]},
                {'Name': 'virtualization-type', 'Values': ['hvm']},
                {'Name': 'state', 'Values': ['available']}
            ]            
        )
        # Sort images by creation date to get the latest
        images = sorted(response['Images'], key=lambda k: k['DeprecationTime'], reverse=True) 
        if images:
            iname = images[0]["Name"].split('/')[-1]
            print(f'Using AMI image {iname}')            
            return images[0]['ImageId']
        else:
            return None 

    def _ec2_ondemand_price(self, instance_type, region='us-west-2'):
        pricing_client = boto3.client('pricing', region_name='us-east-1')
        try:
            region_map = {
                'af-south-1': 'Africa (Cape Town)',
                'ap-east-1': 'Asia Pacific (Hong Kong)',
                'ap-south-1': 'Asia Pacific (Mumbai)',
                'ap-northeast-3': 'Asia Pacific (Osaka)',
                'ap-northeast-2': 'Asia Pacific (Seoul)',
                'ap-southeast-1': 'Asia Pacific (Singapore)',
                'ap-southeast-2': 'Asia Pacific (Sydney)',
                'ap-northeast-1': 'Asia Pacific (Tokyo)',
                'ca-central-1': 'Canada (Central)',
                'eu-central-1': 'Europe (Frankfurt)',
                'eu-west-1': 'Europe (Ireland)',
                'eu-west-2': 'Europe (London)',
                'eu-south-1': 'Europe (Milan)',
                'eu-west-3': 'Europe (Paris)',
                'eu-north-1': 'Europe (Stockholm)',
                'me-south-1': 'Middle East (Bahrain)',
                'sa-east-1': 'South America (São Paulo)',
                'us-gov-east-1': 'AWS GovCloud (US-East)',
                'us-gov-west-1': 'AWS GovCloud (US-West)',
                'us-east-1': 'US East (N. Virginia)',
                'us-east-2': 'US East (Ohio)',
                'us-west-1': 'US West (N. California)',
                'us-west-2': 'US West (Oregon)',
            }

            response = pricing_client.get_products(
                ServiceCode='AmazonEC2',
                Filters=[
                    {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
                    {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region_map.get(region,'')},
                    {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                    {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                    {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
                    {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'},
                ],
                MaxResults=1
            )
            price_list = [json.loads(price_str) for price_str in response['PriceList']]
            on_demand_price = float(price_list[0]['terms']['OnDemand'][list(price_list[0]['terms']['OnDemand'])[0]]['priceDimensions'][list(price_list[0]['terms']['OnDemand'][list(price_list[0]['terms']['OnDemand'])[0]]['priceDimensions'])[0]]['pricePerUnit']['USD'])
            return on_demand_price
        except Exception as e:
            print(f"Error getting on-demand price: {e}")
            return 100 # return a high price to make sure it is not used
        
    def _ec2_current_spot_price(self, instance_type, regions=['us-west-2', 'us-west-1', 'us-east-2', 'us-east-1', 'ca-central-1']):
        PRODUCT = ['Linux/UNIX']
        lowest_price = float('inf')
        lowest_az = None

        print(f'Gathering spot prices from {", ".join(regions)} ... ')
        for region in regions:
            ec2_client = boto3.client(service_name='ec2', region_name=region)           
            response = ec2_client.describe_availability_zones()

            for az in response['AvailabilityZones']:
                spot_response = ec2_client.describe_spot_price_history(
                    InstanceTypes=[instance_type],
                    ProductDescriptions=PRODUCT,
                    MaxResults=1,
                    AvailabilityZone=az['ZoneName']
                )

                if spot_response['SpotPriceHistory']:
                    price = float(spot_response['SpotPriceHistory'][0]['SpotPrice'])
                    if price < lowest_price:
                        lowest_price = price
                        lowest_az = f"{az['ZoneName']}"

        return lowest_price, lowest_az

    def _ec2_get_cheapest_spot_instance(self, cpu_type, vcpus=1, memory_gb=1, region=None):
        ec2 = boto3.client('ec2', region_name=region) if region else self.awssession.client('ec2')
        # Validate CPU type
        if cpu_type not in self.cpu_types:
            return "Invalid CPU type.", None, None
      
        try:
            # Filter instances by vCPUs, memory, and CPU type
            filtered_instances = self._ec2_describe_instance_families(cpu_type, vcpus, memory_gb, region)
            if not filtered_instances:
                return "No instances match the criteria.", None, None   

            # Get current spot prices for filtered instances
            start_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
            instance_ids = [i['InstanceType'] for i in filtered_instances]
            #print('\ninstance_ids:', instance_ids)
            spot_prices = ec2.describe_spot_price_history(
                StartTime=start_time,
                InstanceTypes=instance_ids,
                ProductDescriptions=['Linux/UNIX'],
                MaxResults=len(instance_ids)
            )
            # Find the cheapest instance
            #print(spot_prices['SpotPriceHistory'])
            cheapest_instance = min(spot_prices['SpotPriceHistory'], key=operator.itemgetter('SpotPrice'))
            return cheapest_instance['InstanceType'], cheapest_instance['AvailabilityZone'], float(cheapest_instance['SpotPrice'])
    
        except Exception as e:
            print(f"Error in _ec2_get_cheapest_spot_instance: {e}")
            return None, None, None

    def _create_progress_bar(self, max_value):
        def show_progress_bar(iteration):
            percent = ("{0:.1f}").format(100 * (iteration / float(max_value)))
            length = 50  # adjust as needed for the bar length
            filled_length = int(length * iteration // max_value)
            bar = "█" * filled_length + '-' * (length - filled_length)
            print(f'\r|{bar}| {percent}%', end='\r')
            if iteration == max_value: 
                print()

        return show_progress_bar

    def _ec2_cloud_init_script(self):
        # Define the User Data script
        if self.args.os.lower() in ['rhel', 'amazon']:
            pkgm = 'dnf'
            if self.args.os.lower() == 'rhel':
                self.cfg.defuser = 'rocky'
        if self.args.os.lower() in ['ubuntu', 'debian']:
            pkgm = 'apt'
            if self.args.os.lower() == 'ubuntu':
                self.cfg.defuser = 'ubuntu'
            elif self.args.os.lower() == 'debian':
                self.cfg.defuser = 'admin'
        else:
            pkgm = 'yum'
        long_timezone = self.cfg.get_time_zone()
        newhostname = self.r53_get_next_nodename(self.hostbasename)
        userdata = textwrap.dedent(f'''                                   
        #! /bin/bash
        format_largest_unused_block_devices() {{
            # format the largest unused block device(s) and mount it to /opt or /mnt/scratch
            # if there are multiple unused devices of the same size and their combined size 
            # is larger than the largest unused single block device, they will be combined into 
            # a single RAID0 device and be mounted instead of the largest device
            #
            # Get all unformatted block devices with their sizes
            local devices=$(lsblk --json -n -b -o NAME,SIZE,FSTYPE,TYPE | jq -r '.blockdevices[] | select(.children == null and .type=="disk" and .fstype == null and (.name | tostring | startswith("loop") | not) ) | {{name, size}}')
            # Check if there are any devices to process
            if [[ -z "$devices" ]]; then
                echo "No unformatted block devices found."
                return
            fi
            # Group by size and sum the total size for each group, also count the number of devices in each group
            local grouped_sizes=$(echo "$devices" | jq -s 'group_by(.size) | map({{size: .[0].size, total: (.[0].size * length), count: length, devices: map(.name)}})')
            # Find the configuration with the largest total size
            local best_config=$(echo "$grouped_sizes" | jq 'max_by(.total)')
            # Check if best_config is empty or null
            if [[ -z "$best_config" || "$best_config" == "null" ]]; then
                echo "No suitable block devices found."
                return
            fi
            # Extract the count value
            local count=$(echo "$best_config" | jq '.count')
            # Check if the best configuration is a single device or multiple devices
            if [[ "$count" -eq 1 ]]; then
                # Single largest device
                local largest_device=$(echo "$best_config" | jq -r '.devices[0]')
                echo "/dev/$largest_device"
                mkfs -t xfs "/dev/$largest_device"
                mkdir -p $1
                mount "/dev/$largest_device" $1
                sleep 5
            elif [[ "$count" -gt 1 ]]; then
                # Multiple devices of the same size
                local devices_list=$(echo "$best_config" | jq -r '.devices[]' | sed 's/^/\/dev\//')
                echo "Devices with the largest combined size: $devices_list"
                mdadm --create /dev/md0 --level=0 --raid-devices=$count $devices_list
                mkfs -t xfs /dev/md0
                mkdir -p $1
                mount /dev/md0 $1
                sleep 5
            else
                echo "No uniquely largest block device found."
            fi
        }}
        {pkgm} update -y
        export DEBIAN_FRONTEND=noninteractive
        {pkgm} install -y redis6 
        {pkgm} install -y redis
        {pkgm} install -y python3.11-pip python3.11-devel # for RHEL
        {pkgm} install -y gcc mdadm jq git python3-pip mc
        {pkgm} install -y python3-venv python3-dev rpm2cpio lmod # for Ubuntu
        {pkgm} install -y fuse3
        format_largest_unused_block_devices /opt
        chown {self.cfg.defuser} /opt
        format_largest_unused_block_devices /mnt/scratch
        chown {self.cfg.defuser} /mnt/scratch
        if [[ -f /usr/bin/redis6-server ]]; then
          systemctl enable redis6
          systemctl restart redis6  # juicefs on Amazon linux
        fi
        if [[ -f /usr/bin/redis-server ]]; then
          systemctl enable redis
          # systemctl restart redis # juicefs on RHEL/Ubuntu
        fi
        dnf config-manager --enable crb # enable powertools for RHEL
        {pkgm} install -y epel-release
        {pkgm} check-update
        {pkgm} update -y
        {pkgm} install -y at gcc vim wget python3-psutil
        hostnamectl set-hostname {newhostname}
        timedatectl set-timezone '{long_timezone}'
        loginctl enable-linger {self.cfg.defuser}
        systemctl start atd
        {pkgm} upgrade -y
        {pkgm} install -y docker nodejs-npm Lmod # RHEL
        {pkgm} install -y docker.io nodejs npm # Ubuntu
        {pkgm} install -y lua lua-posix lua-devel tcl-devel
        {pkgm} install -y build-essential tcl-dev tcl       #Ubuntu 22.04 only has lmod 6.6 and EB5 requires 8.0
        {pkgm} install -y lua5.3 lua-bit32 lua-posix lua-posix-dev liblua5.3-0 liblua5.3-dev tcl8.6 tcl8.6-dev libtcl8.6
        dnf group install -y 'Development Tools'
        cd /tmp
        wget https://sourceforge.net/projects/lmod/files/Lmod-8.7.tar.bz2
        tar -xjf Lmod-8.7.tar.bz2
        cd Lmod-8.7 && ./configure && make install        
        if ! [[ -d /usr/share/lmod ]]; then
          ln -s /usr/local/lmod /usr/share/lmod
        fi
        ''').strip()
        return userdata
    
    def _ec2_user_space_script(self, instance_id, fqdn, bscript='~/bootstrap.sh'):
        # Define script that will be installed by ec2-user 
        emailaddr = self.cfg.read('general','email')
        if not emailaddr:
            emailaddr = 'user@domain.edu'
        #short_timezone = datetime.datetime.now().astimezone().tzinfo
        long_timezone = self.cfg.get_time_zone()
        juiceid = f'juice{instance_id.replace("-","")}'
        myhostname = fqdn.split('.')[0]
        if not os.getenv('AWS_ACCESS_KEY_ID'):
            print('No AWS credentials in envionment vars, are you using SSO?')
        return textwrap.dedent(f'''
        #! /bin/bash
        echo "Bootstrapping ASM on {instance_id} ..."
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
          export PATH=~/.local/bin:$PATH
          echo 'export PATH=~/.local/bin:$PATH' >> ~/.bashrc
        fi
        mkdir -p ~/.config/asm
        mkdir -p ~/.local/bin        
        echo 'PS1="\\u@{myhostname}:\\w$ "' >> ~/.bashrc
        echo '#export EC2_INSTANCE_ID={instance_id}' >> ~/.bashrc
        echo '#export AWS_DEFAULT_REGION={self.cfg.aws_region}' >> ~/.bashrc
        echo '#export TZ={long_timezone}' >> ~/.bashrc
        echo '#alias singularity="apptainer"' >> ~/.bashrc
        # Install JuiceFS
        curl -sSL https://d.juicefs.com/install | sh -
        # Install Pixi package manager (Conda alternative)
        export PIXI_HOME=~/.local && curl -fsSL https://pixi.sh/install.sh | bash
        # wait for pip3 to be installed
        echo "Waiting for Python3 pip install ..."        
        until [ -f /usr/bin/pip3 ]; do sleep 3; done; echo "pip3 exists, please wait ..."
        sleep 5
        export PYBIN=/usr/bin/python3
        if [[ -f /usr/bin/python3.11 ]]; then
          export PYBIN=/usr/bin/python3.11
          ln -s /usr/bin/python3.11 ~/.local/bin/python3
        fi
        mkdir -p ~/.config/pip
        echo "[global]\nbreak-system-packages = true" > ~/.config/pip/pip.conf
        $PYBIN -m pip install --upgrade --user pip
        $PYBIN -m pip install --upgrade --user wheel awscli
        $PYBIN -m pip install --user --upgrade boto3 requests
        $PYBIN -m pip install --user psutil
        aws configure set aws_access_key_id {os.getenv('AWS_ACCESS_KEY_ID', '')}
        aws configure set aws_secret_access_key {os.getenv('AWS_SECRET_ACCESS_KEY')}
        aws configure set region {self.cfg.aws_region}
        aws configure --profile {self.cfg.awsprofile} set aws_access_key_id {os.getenv('AWS_ACCESS_KEY_ID','')}
        aws configure --profile {self.cfg.awsprofile} set aws_secret_access_key {os.getenv('AWS_SECRET_ACCESS_KEY', '')}
        aws configure --profile {self.cfg.awsprofile} set region {self.cfg.aws_region}
        sed -i 's/aws_access_key_id [^ ]*/aws_access_key_id /' {bscript}
        sed -i 's/aws_secret_access_key [^ ]*/aws_secret_access_key /' {bscript}
        sed -i 's/^aws configure /#&/' {bscript}
        export AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id)
        export AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key)        
        curl -s https://raw.githubusercontent.com/apptainer/apptainer/main/tools/install-unprivileged.sh | bash -s - ~/.local
        echo '#! /bin/bash' > ~/.local/bin/get-public-ip
        echo 'ETOKEN=$(curl -sX PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")' >> ~/.local/bin/get-public-ip
        cp -f ~/.local/bin/get-public-ip ~/.local/bin/get-local-ip
        cp -f ~/.local/bin/get-public-ip ~/.local/bin/spot-termination-time
        echo 'curl -sH "X-aws-ec2-metadata-token: $ETOKEN" http://169.254.169.254/latest/meta-data/public-ipv4' >> ~/.local/bin/get-public-ip
        echo 'curl -sH "X-aws-ec2-metadata-token: $ETOKEN" http://169.254.169.254/latest/meta-data/local-ipv4' >> ~/.local/bin/get-local-ip
        echo 'curl -sH "X-aws-ec2-metadata-token: $ETOKEN" http://169.254.169.254/latest/meta-data/spot/termination-time' >> ~/.local/bin/spot-termination-time
        chmod +x ~/.local/bin/get-public-ip
        chmod +x ~/.local/bin/get-local-ip
        chmod +x ~/.local/bin/spot-termination-time
        curl -Ls https://raw.githubusercontent.com/dirkpetersen/asm/main/asm.py?token=$(date +%s) -o ~/.local/bin/{self.scriptname}
        curl -Ls https://raw.githubusercontent.com/dirkpetersen/asm/main/asm?token=$(date +%s) -o ~/.local/bin/asm
        curl -Ls https://raw.githubusercontent.com/dirkpetersen/scibob/main/aws-eb.py?token=$(date +%s) -o ~/.local/bin/aws-eb.py
        #curl -Ls https://raw.githubusercontent.com/dirkpetersen/dptests/main/aws-eb/aws-eb.py?token=$(date +%s) -o ~/.local/bin/aws-eb.py        
        curl -Ls https://raw.githubusercontent.com/dirkpetersen/dptests/main/simple-benchmark.py?token=$(date +%s) -o ~/.local/bin/simple-benchmark.py
        chmod +x ~/.local/bin/asm
        chmod +x ~/.local/bin/aws-eb.py
        chmod +x ~/.local/bin/simple-benchmark.py
        $PYBIN ~/.local/bin/simple-benchmark.py > ~/out.simple-benchmark.txt &
        # wait for lmod to be installed
        echo "Waiting for Lmod install ..."
        until [ -f /usr/share/lmod/lmod/init/bash ]; do sleep 3; done; echo "lmod exists, please wait ..."
        echo 'test -d /usr/local/lmod/lmod/init && source /usr/local/lmod/lmod/init/bash' >> ~/.bashrc
        echo 'export MODULEPATH=/opt/eb/modules/all:/opt/eb/modules/lib:/opt/eb/modules/lang:/opt/eb/modules/compiler:/opt/eb/modules/bio' >> ~/.bashrc
        $PYBIN ~/.local/bin/{self.scriptname} config --monitor '{emailaddr}'
        mkdir -p /opt/eb/tmp
        mkdir -p /opt/eb/sources_s3 # rclone mount point
        $PYBIN ~/.local/bin/aws-eb.py download -c {self.args.cputype} >> ~/out.aws-eb.txt 2>&1 &
        if systemctl is-active --quiet redis6 || systemctl is-active --quiet redis; then
          juicefs format --storage s3 --bucket https://s3.{self.cfg.aws_region}.amazonaws.com/{self.cfg.bucket} redis://localhost:6379 {juiceid}
          juicefs config -y --access-key={os.getenv('AWS_ACCESS_KEY_ID', '')} --secret-key={os.getenv('AWS_SECRET_ACCESS_KEY','')} --trash-days 0 redis://localhost:6379
          sudo mkdir -p /mnt/share
          cachedir=/opt/jfsCache
          if [[ -d /mnt/scratch ]]; then
            cachedir=/mnt/scratch/jfsCache
          fi
          sudo /usr/local/bin/juicefs mount -d --cache-dir $cachedir --writeback --cache-size 102400 redis://localhost:6379 /mnt/share # --max-uploads 100 --cache-partial-only
          sudo chown {self.cfg.defuser} /mnt/share       
          #juicefs destroy -y redis://localhost:6379 {juiceid}
          sed -i 's/--access-key=[^ ]*/--access-key=xxx /' {bscript}
          sed -i 's/--secret-key=[^ ]*/--secret-key=yyy /' {bscript}
          sed -i 's/^  juicefs config /#&/' {bscript}
        fi 
        # update DNS if hosted zone is available in route53
        dnszones=$(aws route53 list-hosted-zones)
        dns_zone_name=$(echo $dnszones | jq -r '.HostedZones[0].Name')
        if [[ -n ${{dns_zone_name}} ]]; then
          dns_zone_id=$(echo $dnszones | jq -r '.HostedZones[0].Id' | cut -d'/' -f3)
          pub_ip=$(~/.local/bin/get-public-ip)
          host_s=$(hostname -s)
          host_f=${{host_s}}.${{dns_zone_name%?}}
          JSON53="{{\\"Comment\\":\\"DNS update\\",\\"Changes\\":[{{\\"Action\\":\\"UPSERT\\",\\"ResourceRecordSet\\":{{\\"Name\\":\\"${{host_s}}.${{dns_zone_name}}\\",\\"Type\\":\\"A\\",\\"TTL\\":60,\\"ResourceRecords\\":[{{\\"Value\\":\\"$pub_ip\\"}}]}}}}]}}"
          aws route53 change-resource-record-sets --hosted-zone-id ${{dns_zone_id}} --change-batch "${{JSON53}}"
        fi
        # create certificates with letsencrypt
        python3 -m venv le
        . le/bin/activate
        pip install certbot-dns-route53
        sudo -E /home/{self.cfg.defuser}/le/bin/certbot certonly --dns-route53 --register-unsafely-without-email --agree-tos -d ${{host_s}}.${{dns_zone_name}}
        mkdir -p ~/.jupyter
        sudo cp /etc/letsencrypt/live/${{host_f}}/fullchain.pem ~/.jupyter/fullchain.pem
        sudo cp /etc/letsencrypt/live/${{host_f}}/privkey.pem ~/.jupyter/privkey.pem
        sudo chown {self.cfg.defuser} ~/.jupyter/fullchain.pem
        sudo chown {self.cfg.defuser} ~/.jupyter/privkey.pem
        echo ""
        echo -e "CPU info:"
        lscpu | head -n 20
        printf " CPUs:" && grep -c "processor" /proc/cpuinfo
        ###
        pixi init conda
        cd conda
        pixi add conda
        pixi add python
        pixi add r
        pixi add jupyterlab
        pixi add r-irkernel
        pixi run bash -c "jupyter-lab --ip=$(get-local-ip) --no-browser --autoreload --notebook-dir=~ --certfile=~/.jupyter/fullchain.pem --keyfile=~/.jupyter/privkey.pem > ~/.jupyter.log 2>&1" &
        # echo 'pixi shell --manifest-path ~/conda/pixi.toml' >> ~/.bashrc # causes fork bomb
        sleep 60
        # 
        if [[ -n ${{host_f}} ]]; then
          sed "s/$(get-local-ip)/${{host_f}}/g" ~/.jupyter.log > ~/.jupyter-public.log
          url=$(tail -n 7 ~/.jupyter-public.log | grep ${{host_f}} |  tr -d ' ')
        else
          sed "s/$(get-local-ip)/$(get-public-ip)/g" ~/.jupyter.log > ~/.jupyter-public.log
          url=$(tail -n 7 ~/.jupyter-public.log | grep $(get-public-ip) |  tr -d ' ')
        fi
        echo "" >> ~/.bashrc
        echo 'echo "Access JupyterLab:"' >> ~/.bashrc    
        echo "echo \\" $url\\"" >> ~/.bashrc
        echo 'echo "type this command to activate conda environment:"' >> ~/.bashrc
        echo 'echo "cd ~/conda && pixi shell"' >> ~/.bashrc
        ''').strip()
    
    def _ec2_launch_instance(self, disk_gib, instance_type, iamprofile=None, profile=None):
        
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2 = session.resource('ec2')
        client = session.client('ec2')
        
        # Define the block device mapping for an EBS volume to be attached to the instance
        block_device_mappings = []
        if disk_gib > 0:
            block_device_mappings = [
            {
                'DeviceName': '/dev/sdm',  # Ensure that this device name is supported and free in your EC2 instance
                'Ebs': {
                    'VolumeSize': disk_gib,  # Volume size in GiB (1 TB = 1024 GiB)
                    'DeleteOnTermination': True,  # True if the volume should be deleted after instance is terminated
                    'VolumeType': 'gp3',  # The type of volume to create (gp3 is generally a good default)
                    'Iops': 3000,  # Provisioned IOPS for the volume
                    'Throughput': 750,  # Throughput in MB/s
                },
            }]
                     
        if not instance_type:
            print("No suitable instance type found!")
            return False
      
        # Create a new EC2 key pair
        awsacc, _, username = self.get_aws_account_and_user_id()
        keyname = f'{self.cfg.ssh_key_name}-{username}'
        key_path = os.path.join(self.cfg.config_root,'cloud',
                f'{self.cfg.ssh_key_name}-{awsacc}-{username}.pem')
        if not os.path.exists(key_path):
            if not self.args.forcesshkey:
                print(f'ssh key {key_path} not found.')
                print('You can use option --force-sshkey to create a new one in AWS')
                sys.exit(1)
            try:
                client.describe_key_pairs(KeyNames=[keyname])
                # If the key pair exists, delete it
                client.delete_key_pair(KeyName=keyname)
            except client.exceptions.ClientError:
                # Key pair doesn't exist in AWS, no need to delete
                pass                        
            key_pair = ec2.create_key_pair(KeyName=keyname, KeyType='ed25519')
            os.makedirs(os.path.join(self.cfg.config_root,'cloud'),exist_ok=True)            
            with open(key_path, 'w') as key_file:
                key_file.write(key_pair.key_material)
            os.chmod(key_path, 0o600)  # Set file permission to 600

        if self.args.os.lower() == 'amazon':
            imageid = self._ec2_get_latest_amazon_linux_ami(profile)
        elif self.args.os.lower() == 'ubuntu':
            imageid = self._ec2_get_latest_ubuntu_lts_ami(profile)
        elif self.args.os.lower() == 'rhel':
            imageid = self._ec2_get_latest_rocky_linux_ami(profile)
        else:
            imageid = self._ec2_get_latest_other_linux_ami(self.args.os, profile)
        
        if not imageid:
            print(f'No {self.args.os} image found that matches the criteria.')
            sys.exit(1)
            #return None, None

        #print(f'Using {self.args.os} image id: {imageid}')

        #print(f'*** userdata-script:\n{self._ec2_user_data_script()}')

        iam_instance_profile={}
        if iamprofile:
            iam_instance_profile={
                'Name': iamprofile  # Use the instance profile name
            }        
        print(f'IAM Instance profile: {iamprofile}.')

        # iam_instance_profile = {}
        #print(f'AWS Region: {self.cfg.aws_region}')
        
        instance_type, az, price_spot = self._ec2_get_cheapest_spot_instance(self.args.cputype, self.args.vcpus, self.args.mem)
        
        if self.args.instancetype:
            instance_type = self.args.instancetype             
            price_spot, az = self._ec2_current_spot_price(instance_type, [self.cfg.aws_region])
        price_ondemand = float(self._ec2_ondemand_price(instance_type, self.cfg.aws_region))
        numvcpus = self._ec2_get_num_vcpus(instance_type)   

        print(f'{instance_type} in {az} costs ${price_ondemand:.4f} as on-demand and ${price_spot:.4f} as spot. (${price_spot/numvcpus:.4f} per vCPU)')

        if self.args.az:
            az = self.args.az
    
        for i in range(2):
            try:            
                if price_ondemand < price_spot*1.05:
                    print('Oops, On-demand pricing lower than Spot.')
                    myinstance = "on-demand instance"
                    marketoptions = {}
                    placementdict = {}
                elif self.args.ondemand:
                    myinstance = "on-demand instance"
                    marketoptions = {}
                    placementdict = {}
                else:
                    myinstance = "spot instance"
                    marketoptions = {
                        'MarketType': 'spot',
                        'SpotOptions': {
                            'MaxPrice': str(price_spot*1.05),
                            'SpotInstanceType': 'one-time',
                            'InstanceInterruptionBehavior': 'terminate'
                        }
                    }
                    placementdict = {'AvailabilityZone': az}
                    #placementdict = {}
                    
                # Create EC2 instance
                
                instance = ec2.create_instances(
                    ImageId=imageid,
                    MinCount=1,
                    MaxCount=1,
                    InstanceType=instance_type,
                    KeyName=keyname,
                    UserData=self._ec2_cloud_init_script(),
                    IamInstanceProfile = iam_instance_profile,
                    BlockDeviceMappings = block_device_mappings,
                    TagSpecifications=[
                        {
                            'ResourceType': 'instance',
                            'Tags': [{'Key': 'Name', 'Value': 'ASMSelfDestruct'}]
                        }
                    ],
                    InstanceMarketOptions=marketoptions,
                    Placement=placementdict
                )[0]
                break
            
            except botocore.exceptions.ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'AccessDenied':
                    print(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
                    sys.exit(1)
                elif error_code == 'SpotMaxPriceTooLow':
                    errmsg = e.response['Error']['Message']
                    print (f"{errmsg}")
                    price_spot = self._extract_last_float(errmsg)
                    print(f'Trying again with new price: ${price_spot:.4f}')               
                elif error_code == 'OptInRequired':
                    print(f"Client Error: {e.response['Error']['Message']}")
                    print(f"Please go to the url and accept.")
                    sys.exit(1)
                elif error_code == 'InsufficientInstanceCapacity':
                    print(f"{e.response['Error']['Message']}")
                    print(f"Please try again later or use the --az, --on-demand or --instance-type options.")
                    sys.exit(3) 
                else:
                    print(f'ClientError in _ec2_launch_instance: {e}')
                    raise(e)
                    sys.exit(1)
                continue
        
            except Exception as e:
                #print(f'Error in _ec2_launch_instance: {e}')
                raise(e)
                #sys.exit(1)
    
        # Use a waiter to ensure the instance is running before trying to access its properties
        instance_id = instance.id    

        # tag the instance for cost explorer 
        tag = {
            'Key': 'INSTANCE_ID',
            'Value': instance_id
        }
        try:
            ec2.create_tags(Resources=[instance_id], Tags=[tag])
        except Exception as e:
            self.cfg.printdbg('Error creating Tags: {e}')
            
        print(f'Launching {myinstance} {instance_id} ... please wait ...')
        
        max_wait_time = 300  # seconds
        delay_time = 10  # check every 10 seconds, adjust as needed
        max_attempts = max_wait_time // delay_time

        waiter = client.get_waiter('instance_running')
        progress = self._create_progress_bar(max_attempts)

        for attempt in range(max_attempts):
            try:
                waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': delay_time, 'MaxAttempts': 1})
                progress(attempt)
                break
            except botocore.exceptions.WaiterError:
                progress(attempt)
                continue
        print('')
        instance.reload()    

        grpid = self._ec2_create_and_attach_security_group(instance_id, profile)
        if grpid:
            print(f'Security Group "{grpid}" attached.') 
        else:
            print('No Security Group ID created.')
        instance.wait_until_running()
        print(f'Instance IP: {instance.public_ip_address}')

        last_instance = self.r53_register_host(self.hostbasename, instance.public_ip_address)

        if last_instance != instance.public_ip_address:
            print(f'FQDN: {last_instance}')

        self.cfg.write('cloud', 'ec2_last_instance', last_instance)

        return instance_id, last_instance, instance.public_ip_address

    def _ec2_get_running_paused_instance_ips(self):
        ec2 = self.awssession.client('ec2')
        instance_ips = set()
        response = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
        )
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                public_ip = instance.get('PublicIpAddress')
                if public_ip:
                    instance_ips.add(public_ip)
        return instance_ips
    

    def _ec2_get_num_vcpus(self, instance_type):
        try:
            ec2 = self.awssession.client('ec2')        
            response = ec2.describe_instance_types(InstanceTypes=[instance_type])
            return response['InstanceTypes'][0]['VCpuInfo']['DefaultVCpus']    
        except Exception as e:
            print(f'Error in _ec2_get_num_vcpus: {e}')
            return None

    def ec2_terminate_instance(self, ip, profile=None):
        # terminate instance  
        # with ephemeral (local) disk for a temporary restore 

        ip = self.r53_get_ip(ip)

        ec2 = self.awssession.client('ec2')
        #ips = self.ec2_list_ips(self, 'Name', 'ASMSelfDestruct')
        # Use describe_instances with a filter for the public IP address to find the instance ID
        filters = [{
            'Name': 'network-interface.addresses.association.public-ip',
            'Values': [ip]
        }]

        if not ip.startswith('i-'): # this an ip and not an instance ID
            try:
                response = ec2.describe_instances(Filters=filters)        
            except botocore.exceptions.ClientError as e: 
                print(f'Error: {e}')
                return False
            # Check if any instances match the criteria
            instances = [instance for reservation in response['Reservations'] for instance in reservation['Instances']]        
            if not instances:
                print(f"No EC2 instance found with public IP: {ip}")
                return 
            # Extract instance ID from the instance
            instance_id = instances[0]['InstanceId']
        else:    
            instance_id = ip
        # Terminate the instance
        ec2.terminate_instances(InstanceIds=[instance_id])
        
        print(f"EC2 Instance {instance_id} ({ip}) is being terminated !")

    def ec2_get_default_user(self, ip_or_host, instance_list=None):
        # get the default user for the OS, e.g. ubuntu, ec2-user, centos, ...        
        ip_or_host = self.r53_get_short_host_or_ip(ip_or_host)        
        if not instance_list:
            instance_list = self.ec2_list_instances('Name', 'ASMSelfDestruct')
        for inst in instance_list:
            #print(f'Instaaaance {inst[3]}')
            if inst[0] == ip_or_host:
                if inst[3].startswith('ubuntu'):
                    return 'ubuntu'
                elif inst[3].startswith('rhel'):
                    return 'ec2-user'
                elif inst[3].startswith('al'):
                    return 'ec2-user'
                elif inst[3].startswith('debian'):
                    return 'admin'
                elif inst[3].startswith('rocky'):
                    return 'rocky'
                else:
                    return 'ec2-user'
        return 'unknown'

    def ec2_list_instances(self, tag_name, tag_value):
        """
        List all IP addresses of running EC2 instances with a specific tag name and value.
        :param tag_name: The name of the tag
        :param tag_value: The value of the tag
        :return: List of IP addresses
        """
        #session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        try:
            ec2 = self.awssession.client('ec2')        
            
            # Define the filter
            filters = [
                {
                    'Name': 'tag:' + tag_name,
                    'Values': [tag_value]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
            
            # Make the describe instances call
        
            response = ec2.describe_instances(Filters=filters)
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied! Please check your IAM permissions. \n   Error: {e}')
            else:
                print(f'ec2_list_instances, aws client Error: {e}')
            return []
        except Exception as e:
            print(f'ec2_list_instances(), {type(e).__name__} Error: {e}')
            if type(e).__name__ == "TokenRetrievalError":
                print(f'Please run "aws ssh login" to refresh your AWS credentials.')
                sys.exit(1)
            #traceback.print_exc()   # This prints the stack trace
            return []
        
        ilist = []    
        # Extract IP addresses
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                status = '(Running)'
                if self.monitor_has_instance_failed(instance['InstanceId'], False):
                    status = '(Failed)'
                else:
                    status = '(OK)'

                # Get the AMI ID used by the instance
                ami_id = instance['ImageId']

                # Retrieve information about the AMI
                ami_response = ec2.describe_images(ImageIds=[ami_id])
                ami_info = ami_response['Images'][0]
                # Extract OS information from the AMI description or name
                #print(ami_info)
                #os_info = ami_info.get('Description') or ami_info.get('Name')
                os_info = ami_info.get('Name')
                if os_info:
                    os_info = self.cfg.parse_version_string(os_info.split('/')[-1]) #.replace('ubuntu/images/hvm-ssd/','').strip()     
                # lt = ''
                # if instance['LaunchTime']:
                #     lt = instance['LaunchTime'].strftime("%m-%d %H:%M")
                now = datetime.datetime.now(datetime.timezone.utc) 
                uptime = now - instance['LaunchTime']  # Calculate uptime       
                # Convert uptime to days, hours, and minutes
                uptime_days = uptime.days
                uptime_hours = uptime.seconds // 3600
                uptime_minutes = (uptime.seconds % 3600) // 60
                uptime_formatted = f"{uptime_days:02d}-{uptime_hours:02d}:{uptime_minutes:02d}"

                row = [instance['PublicIpAddress'],
                       instance['InstanceId'],
                       instance['InstanceType'],
                       os_info.lower(),
                       uptime_formatted,
                       status
                       ]
                ilist.append(row)
        ilist.sort(key=lambda x: x[-2],reverse=True)  # Assuming the last element in each row is the launch time
        ilist = self.r53_get_short_hostnames([], ilist)
        return ilist
    
    def _r53_get_a_records(self, host_basename=None):
        try:
            hosted_zones = self.r53.list_hosted_zones()['HostedZones']
            if not hosted_zones:
                return None
            paginator = self.r53.get_paginator('list_resource_record_sets')
            pattern = rf"^(?:{host_basename})" if host_basename else r"^"
            for page in paginator.paginate(HostedZoneId=hosted_zones[0]['Id']):
                for record_set in page['ResourceRecordSets']:
                        if record_set['Type'] == 'A' and re.match(pattern, record_set['Name']):
                            yield record_set
        except Exception as e:
            print(f'Error in _r53_get_a_records: {e}')
            return None

    def r53_get_next_nodename(self, base_name, dns_records=None):
        # check if basename exists in dns and add the highest not existing number to it
        if not dns_records:
            dns_records = self._r53_get_a_records(base_name)
        pattern = rf"^{base_name}(\d*)\." # Match the base name and any number following it up to dot
        nodeids = []
        for record in dns_records:
            match = re.search(pattern, record['Name'])
            if match:
                num = match.group(1)
                if not num:
                    num = '0'
                nodeids.append(int(num))
        if not nodeids:
            return base_name
        next_id = max(nodeids, key=int) + 1
        return base_name + str(next_id)

    def r53_get_first_domain(self):
        try:            
            hosted_zones = self.r53.list_hosted_zones()['HostedZones']
            if not hosted_zones:
                return None
            return hosted_zones[0]['Name'].rstrip('.')
        except Exception as e:
            print(f'Error in r53_get_first_domain: {e}')
            return None

    def r53_register_host(self, node_basename, ip_address):
        """
        Registers a nodename as a host name A record in the first found hosted zone on Route 53.
        increments the number in the nodename if it already exists.
        :param nodename: The name of the node to register.
        :param ip_address: IP address for the A record, default is '0.0.0.0'.
        :return: FQDN if successful, original ip address otherwise.
        """

        try:            
            hosted_zones = self.r53.list_hosted_zones()['HostedZones']
            if not hosted_zones:
                return ip_address

            # Use the first hosted zone
            zone_id = hosted_zones[0]['Id']
            zone_name = hosted_zones[0]['Name']

            a_records = self._r53_get_a_records()
            newhost = self.r53_get_next_nodename(node_basename, a_records)

            response = self.r53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': newhost + '.' + zone_name,
                                'Type': 'A',
                                'TTL': 60,
                                'ResourceRecords': [{'Value': ip_address}]
                            }
                        }
                    ]
                }
            )

            # Check if the request was successful
            if response['ChangeInfo']['Status'] == 'PENDING':
                return newhost + '.' + zone_name.rstrip('.')
        except Exception as e:
            print(f'Error in r53_register_host: {e}')

        return ip_address

    
    def r53_get_short_hostnames(self, ip_addresses, ilist=None):
        """
        Returns a list of short hostnames based on 'A' records for given IP addresses.
        If a short hostname cannot be found, returns the IP address instead.
        If ip_addresses is an empty list and ilist is not None, processes ilist where each
        sublist's first element is an IP address.
        """
        a_records = list(self._r53_get_a_records())  # Assuming _r53_get_a_records is a generator
        ip_to_hostname = {rec['ResourceRecords'][0]['Value']: rec['Name'] for rec in a_records if rec['Type'] == 'A'}

        if not ip_addresses and ilist is not None:
            for sublist in ilist:
                if sublist and isinstance(sublist, list):
                    ip = sublist[0]
                    hostname = ip_to_hostname.get(ip, ip)
                    short_hostname = hostname.rstrip('.').split('.')[0] if hostname != ip else ip
                    sublist[0] = short_hostname
            return ilist
        else:
            short_hostnames = []
            for ip in ip_addresses:
                hostname = ip_to_hostname.get(ip, ip)
                short_hostname = hostname.rstrip('.').split('.')[0] if hostname != ip else ip
                short_hostnames.append(short_hostname)
            return short_hostnames       

    def r53_get_ip(self, ip_or_hostname):
        try:
            if self.cfg.is_ipv4_address(ip_or_hostname):
                return ip_or_hostname
            if '.' in ip_or_hostname:
                return socket.gethostbyname(ip_or_hostname)
            return socket.gethostbyname(f'{ip_or_hostname}.{self.r53_get_first_domain()}')
        except Exception as e:
            print(f'Error in r53_get_ip: {e}')
            return ip_or_hostname
        
    def r53_get_fqdn_or_ip(self, ip_or_hostname):
        if self.cfg.is_ipv4_address(ip_or_hostname):
            return ip_or_hostname
        if '.' in ip_or_hostname:
            return ip_or_hostname
        else:
            dom = self.r53_get_first_domain()
            if dom:
                return f'{ip_or_hostname}.{dom}'
            else:
                return ip_or_hostname
            
    def r53_cleanup(self, host_basename):
        try:            
            active_ips = self._ec2_get_running_paused_instance_ips()
            a_records = self._r53_get_a_records(host_basename)

            hosted_zones = self.r53.list_hosted_zones()['HostedZones']
            if not hosted_zones:
                return None
            
            # Use the first hosted zone
            zone_id = hosted_zones[0]['Id']
            unused_records = []
            cleaned_ips = []    

            for record in a_records:
                for record_value in record.get('ResourceRecords', []):
                    ip = record_value['Value']
                    if ip not in active_ips:
                        cleaned_ips.append(ip)
                        unused_records.append({'Action': 'DELETE', 'ResourceRecordSet': record})

            if unused_records:
                self.r53.change_resource_record_sets(
                    HostedZoneId=zone_id,
                    ChangeBatch={'Changes': unused_records}
                )
            print(f'Route 53 cleanup complete.')
            if cleaned_ips:
                   print(f'Removed entries: {", ".join(cleaned_ips)}')
            else:
                print('No entries removed.')
        except Exception as e:
            print(f'Error in r53_cleanup: {e}')
            return None

    def r53_get_short_host_or_ip(self, ip_or_hostname):
        if self.cfg.is_ipv4_address(ip_or_hostname):
            return ip_or_hostname
        if not '.' in ip_or_hostname:
            return ip_or_hostname
        else:
            return ip_or_hostname.split('.')[0]

    def ssh_execute(self, user, host, command=None):
        """Execute an SSH command on the remote server."""
        SSH_OPTIONS = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR"
        awsacc, _, username = self.get_aws_account_and_user_id()
        key_path = os.path.join(self.cfg.config_root,'cloud',
                f'{self.cfg.ssh_key_name}-{awsacc}-{username}.pem')
        host = self.r53_get_fqdn_or_ip(host)
        cmd = f"ssh {SSH_OPTIONS} -i '{key_path}' {user}@{host}"
        if command:
            cmd += f" '{command}'"
            try:
                result = subprocess.run(cmd, shell=True, text=True) #capture_output=True
                return result
            except:
                print(f'Error executing "{cmd}."')
        else:
            subprocess.run(cmd, shell=True, text=True) #capture_output=False
        self.cfg.printdbg(f'ssh command line: {cmd}')
        return None
                
    def ssh_upload(self, user, host, local_path, remote_path, is_string=False, cap_output=True):
        """Upload a file to the remote server using SCP."""
        SSH_OPTIONS = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR -o BatchMode=yes"
        awsacc, _, username = self.get_aws_account_and_user_id()
        key_path = os.path.join(self.cfg.config_root,'cloud',
                f'{self.cfg.ssh_key_name}-{awsacc}-{username}.pem')
        if is_string:
            # the local_path is actually a string that needs to go into temp file 
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp:
                temp.write(local_path)
                local_path = temp.name
        host = self.r53_get_fqdn_or_ip(host)
        cmd = f"scp {SSH_OPTIONS} -i '{key_path}' {local_path} {user}@{host}:{remote_path}"
        #cmdlist = shlex.split(cmd)        
        try:
            result = subprocess.run(cmd, shell=True, text=True, capture_output=cap_output)
            if is_string:
                os.remove(local_path)            
            return result            
        except Exception as e:
            print(f'Error executing "{cmd}" in ssh_upload: {e}')
        return None

    def ssh_download(self, user, host, remote_path, local_path, cap_output=True):
        """Upload a file to the remote server using SCP."""
        SSH_OPTIONS = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o LogLevel=ERROR -o BatchMode=yes"
        awsacc, _, username = self.get_aws_account_and_user_id()
        key_path = os.path.join(self.cfg.config_root,'cloud',
                f'{self.cfg.ssh_key_name}-{awsacc}-{username}.pem')
        host = self.r53_get_fqdn_or_ip(host)
        cmd = f"scp {SSH_OPTIONS} -i '{key_path}' {user}@{host}:{remote_path} {local_path}"        
        try:
            result = subprocess.run(cmd, shell=True, text=True, capture_output=cap_output)
            return result
        except Exception as e:
            print(f'Error executing "{cmd}" in ssh_download: {e}')
        return None            

    def ssh_add_key_to_remote_host(self, private_key_path, user, host):
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            # Generate the public key from the source private key
            subprocess.run(['ssh-keygen', '-y', '-f', private_key_path], stdout=temp_file)
            temp_file.flush()
            # Read the generated public key
            with open(temp_file.name, 'r') as pub_key_file:
                public_key = pub_key_file.read().strip()
        # SSH command to check if the key exists and append it if not
        check_and_append_command = (
            f"grep -q -F '{public_key}' ~/.ssh/authorized_keys || "
            f"echo '{public_key}' >> ~/.ssh/authorized_keys"
        )
        ret = self.ssh_execute(user, host, command=check_and_append_command)
        print (f'Added public key to {user}@{host}: {public_key}')
        return ret

    def send_email_ses(self, sender, to, subject, body, profile=None):
        # Using AWS ses service to send emails
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ses = session.client("ses")

        ses_verify_requests_sent = []
        if not sender:
            sender = self.cfg.read('general', 'email')
        if not to:
            to = self.cfg.read('general', 'email')
        if not to or not sender:
            print('from and to email addresses cannot be empty')
            return False
        ret = self.cfg.read('cloud', 'ses_verify_requests_sent')
        if isinstance(ret, list):
            ses_verify_requests_sent = ret
        else:
            ses_verify_requests_sent.append(ret)

        verified_email_addr = []
        try:
            response = ses.list_verified_email_addresses()
            verified_email_addr = response.get('VerifiedEmailAddresses', [])
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied to SES advanced features! Please check your IAM permissions. \nError: {e}')
            else:
                print(f'Client Error: {e}')
        except Exception as e:
            print(f'Other Error: {e}')
    
        checks = [sender, to]
        checks = list(set(checks)) # remove duplicates
        checked = []

        try:
            for check in checks:
                if check not in verified_email_addr and check not in ses_verify_requests_sent:
                    response = ses.verify_email_identity(EmailAddress=check)
                    checked.append(check)
                    print(f'{check} was used for the first time, verification email sent.')
                    print(f'Please have {check} check inbox and confirm email from AWS.\n')

        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied to SES advanced features! Please check your IAM permissions. \nError: {e}')
            else:
                print(f'Client Error: {e}')
        except Exception as e:
            print(f'Other Error: {e}')
        
        self.cfg.write('cloud', 'ses_verify_requests_sent', checked)
        try:
            response = ses.send_email(
                Source=sender,
                Destination={
                    'ToAddresses': [to]
                },
                Message={
                    'Subject': {
                        'Data': subject
                    },
                    'Body': {
                        'Text': {
                            'Data': body
                        }
                    }
                }
            )
            print(f'Sent email "{subject}" to {to}!')
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'MessageRejected':
                print(f'Message was rejected, Error: {e}')
            elif error_code == 'AccessDenied':
                self.cfg.printdbg(f'Access denied to SES advanced features! Please check your IAM permissions. \nError: {e}')
                if not args.debug:
                    print (' Cannot use SES email features to send you status messages: AccessDenied')                
            else:
                print(f'Client Error: {e}')
            return False
        except Exception as e:
            print(f'Other Error: {e}')
            return False
        return True

    def send_ec2_costs(self, instance_id, profile=None):
        pass

    def _ec2_create_iam_costexplorer_ses(self, instance_id ,profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        iam = session.client('iam')
        ec2 = session.client('ec2')

        # Define the policy
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ses:SendEmail",
                    "Resource": "*"
                },                
                {
                    "Effect": "Allow",
                    "Action": [
                        "ce:*",              # Permissions for Cost Explorer
                        "ce:GetCostAndUsage", # all
                        "ec2:Describe*",     # Basic EC2 read permissions
                    ],
                    "Resource": "*"
                }
            ]
        }

        # Step 1: Create the policy in IAM
        policy_name = "CostExplorerSESPolicy"

        policy_arn = self._ec2_create_or_get_iam_policy(
            policy_name, policy_document, profile)
                
        # Step 2: Retrieve the IAM instance profile attached to the EC2 instance
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance_data = response['Reservations'][0]['Instances'][0]
        if 'IamInstanceProfile' not in instance_data:
            print(f"No IAM Instance Profile attached to the instance: {instance_id}")
            return False

        instance_profile_arn = response['Reservations'][0]['Instances'][0]['IamInstanceProfile']['Arn']

        # Extract the instance profile name from its ARN
        instance_profile_name = instance_profile_arn.split('/')[-1]

        # Step 3: Fetch the role name from the instance profile
        response = iam.get_instance_profile(InstanceProfileName=instance_profile_name)
        role_name = response['InstanceProfile']['Roles'][0]['RoleName']

        # Step 4: Attach the desired policy to the role
        try:
            iam.attach_role_policy(
                RoleName=role_name,
                PolicyArn=policy_arn
            )
            print(f"Policy {policy_arn} attached to role {role_name}")
        except iam.exceptions.NoSuchEntityException:
            print(f"Role {role_name} does not exist!")
        except iam.exceptions.InvalidInputException as e:
            print(f"Invalid input: {e}")
        except Exception as e:
            print(f"Other Error: {e}")


    def _ec2_create_iam_self_destruct_role(self, profile):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        iam = session.client('iam')

        # Step 1: Create IAM policy
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ec2:TerminateInstances",
                    "Resource": "*",
                    "Condition": {
                        "StringEquals": {
                            "ec2:ResourceTag/Name": "ASMSelfDestruct"
                        }
                    }
                }
            ]
        }
        policy_name = 'SelfDestructPolicy'
        
        policy_arn = self._ec2_create_or_get_iam_policy(
            policy_name, policy_document, profile)

        # Step 2: Create an IAM role and attach the policy
        trust_relationship = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }

        role_name = 'SelfDestructRole'
        try:
            iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_relationship, indent=4),
                Description='Allows EC2 instances to call AWS services on your behalf.'
            )
        except iam.exceptions.EntityAlreadyExistsException:
            print ('IAM SelfDestructRole already exists.')            

        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )

        return True
    

    def _get_ec2_metadata(self, metadata_entry):

        # request 'local-hostname', 'public-hostname', 'local-ipv4', 'public-ipv4'

        # Define the base URL for the EC2 metadata service
        base_url = "http://169.254.169.254/latest/meta-data/"

        # Request a token with a TTL of 60 seconds
        token_url = "http://169.254.169.254/latest/api/token"
        token_headers = {"X-aws-ec2-metadata-token-ttl-seconds": "60"}
        try:
            token_response = requests.put(token_url, headers=token_headers, timeout=2)
        except Exception as e:
            print(f'Other Error: {e}')
            return ""
        token = token_response.text

        # Use the token to retrieve the specified metadata entry
        headers = {"X-aws-ec2-metadata-token": token}
        try:
            response = requests.get(base_url + metadata_entry, headers=headers, timeout=2)
        except Exception as e:
            print(f'Other Error: {e}')
            return ""            

        if response.status_code != 200:
            print(f"Error: Failed to retrieve metadata for entry: {metadata_entry}. HTTP Status Code: {response.status_code}")
            return ""
    
        return response.text

    def get_ec2_my_instance_family(self):
        instance_type =self._get_ec2_metadata('instance-type')
        return instance_type.split('.')[0]


    def iam_get_current_user_arn(self):
        try:
            iam = self.awssession.client('iam')
            user = iam.get_user()
            return user['User']['Arn']
        except iam.exceptions.ClientError as e:
            # This might happen if you're using root credentials or an assumed role
            return self.awssession.client('sts').get_caller_identity()['Arn']

    def iam_can_principal_assume_role(self, principal_arn, trust_policy):
        try:
            policy_doc = json.loads(trust_policy)
            for statement in policy_doc.get("Statement", []):
                if statement.get("Effect") == "Allow":
                    principal = statement.get("Principal")
                    if isinstance(principal, dict):
                        # Check if principal is directly mentioned in the principal
                        if "AWS" in principal:
                            principal_aws = principal["AWS"]
                            if isinstance(principal_aws, list):
                                if principal_arn in principal_aws:
                                    return True
                            elif principal_aws == principal_arn:
                                return True
        except json.JSONDecodeError:
            pass
        return False

    def iam_list_roles_for_principal(self, principal_arn):
        iam = self.awssession.client('iam')
        roles_for_principal = []

        try:
            # List all roles
            roles = iam.list_roles()
            for role in roles.get('Roles', []):
                role_name = role['RoleName']
                # Get the trust policy of each role
                trust_policy = role['AssumeRolePolicyDocument']
                if self.iam_can_principal_assume_role(principal_arn, json.dumps(trust_policy)):
                    roles_for_principal.append(role_name)
        except Exception as e:
            print(f"Error: {str(e)}")
        
        return roles_for_principal

    def iam_list_roles_for_user_groups(self, user_name):
        iam = self.awssession.client('iam')
        roles_for_user_groups = []

        try:
            # List groups for the user
            groups = iam.list_groups_for_user(UserName=user_name)
            for group in groups.get('Groups', []):
                group_policies = iam.list_attached_group_policies(GroupName=group['GroupName'])
                for policy in group_policies.get('AttachedPolicies', []):
                    policy_arn = policy['PolicyArn']
                    policy_version = iam.get_policy_version(
                        PolicyArn=policy_arn,
                        VersionId=iam.get_policy(PolicyArn=policy_arn)['Policy']['DefaultVersionId']
                    )
                    policy_document = policy_version['PolicyVersion']['Document']
                    roles_for_user_groups.extend(self.iam_list_roles_for_principal(json.dumps(policy_document)))
        except Exception as e:
            print(f"Error: {str(e)}")
        
        return roles_for_user_groups
    
    def iam_list_my_roles(self):

        # Get the current user's ARN
        current_user_arn = self.iam_get_current_user_arn()

        # If the current user is root, handle accordingly
        if current_user_arn.split(':')[5].startswith('root'):
            print("Currently using root user.")
            # Note: Root user has implicit access and does not have groups
            roles_for_current_user = self.iam_list_roles_for_principal(current_user_arn)
        else:
            # Extract user name from ARN for non-root users
            current_user_name = current_user_arn.split('/')[-1]
            
            # List roles that the user can assume directly or through groups
            roles_for_current_user = list(set(
                self.iam_list_roles_for_principal(current_user_arn) + 
                self.iam_list_roles_for_user_groups(current_user_name)
            ))
        return roles_for_current_user

    # def iam_list_external_accounts_for_role(self, role_name):
    #     iam = self.awssession.client('iam')
    #     myaccount, *_ = self.get_aws_account_and_user_id()
    #     account_ids = []

    #     # Get role details
    #     role_details = iam.get_role(RoleName=role_name)
    #     role_policies = role_details['Role'].get('AttachedPolicies', [])

    #     # Check managed policies
    #     for policy in role_policies:
    #         policy_arn = policy['PolicyArn']
    #         policy_version = iam.get_policy(PolicyArn=policy_arn)['Policy']['DefaultVersionId']
    #         policy_document = iam.get_policy_version(PolicyArn=policy_arn, VersionId=policy_version)['PolicyVersion']['Document']
    #         account_ids.extend(self.extract_account_ids(policy_document, myaccount))

    #     # Check inline policies
    #     inline_policies = iam.list_role_policies(RoleName=role_name)['PolicyNames']
    #     for policy_name in inline_policies:
    #         policy_document = iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)['PolicyDocument']
    #         account_ids.extend(self._iam_extract_account_ids(policy_document, myaccount))

    #     return list(set(account_ids))  # Remove duplicates
    
    def iam_list_external_accounts_and_roles(self):
        # returns a list of dictionaries of external accounts and roles that the current user has access to
        iam = self.awssession.client('iam')
        myaccount, _, username = self.get_aws_account_and_user_id()
        #print(myaccount, username)
        accounts_and_roles = []

        try:
            # Check managed policies attached to user
            user_policies = iam.list_attached_user_policies(UserName=username)['AttachedPolicies']
            for policy in user_policies:
                accounts_and_roles.extend(self._iam_process_latest_policy_version(iam, policy, myaccount))

            # Check inline policies attached to user
            inline_policies = iam.list_user_policies(UserName=username)['PolicyNames']
            for policy_name in inline_policies:
                policy_document = iam.get_user_policy(UserName=username, PolicyName=policy_name)['PolicyDocument']
                accounts_and_roles.extend(self._iam_extract_accounts_roles(policy_document, myaccount))

            # Check policies from groups the user is a part of
            groups = iam.list_groups_for_user(UserName=username)['Groups']
            for group in groups:
                group_name = group['GroupName']
                # Managed policies in group
                group_policies = iam.list_attached_group_policies(GroupName=group_name)['AttachedPolicies']
                for policy in group_policies:
                    accounts_and_roles.extend(self._iam_process_latest_policy_version(iam, policy, myaccount))

                # Inline policies in group
                inline_group_policies = iam.list_group_policies(GroupName=group_name)['PolicyNames']
                for policy_name in inline_group_policies:
                    policy_document = iam.get_group_policy(GroupName=group_name, PolicyName=policy_name)['PolicyDocument']
                    accounts_and_roles.extend(self._iam_extract_accounts_roles(policy_document, myaccount))

            # return accounts_and_roles        
            return list(set(accounts_and_roles))  # Remove duplicates
        except Exception as e:          
            print(f"Error in iam_list_external_accounts_and_roles(): {str(e)}")
            return []

    def _iam_process_latest_policy_version(self, iam, policy, myaccount):
        policy_arn = policy['PolicyArn']
        policy_version = iam.get_policy(PolicyArn=policy_arn)['Policy']['DefaultVersionId']
        policy_document = iam.get_policy_version(PolicyArn=policy_arn, VersionId=policy_version)['PolicyVersion']['Document']
        return self._iam_extract_accounts_roles(policy_document, myaccount)    

    def _iam_extract_accounts_roles(self, policy_document, myaccount):
        account_ids = []
        for statement in policy_document['Statement']:
            if 'Resource' in statement:
                resources = statement['Resource']
                if not isinstance(resources, list):
                    resources = [resources]  # Ensure it's a list
                for resource in resources:
                    if isinstance(resource, str) and resource.startswith('arn:aws:iam::') and 'role/' in resource:
                        parts = resource.split(':')
                        account_id = parts[4]
                        role_name = parts[-1].split('/')[-1]
                        if account_id == '*' or account_id == myaccount:
                            continue  # Skip if account is '*' or the same as myaccount
                        account_ids.append({'account': account_id, 'role': role_name})               
        return account_ids

    def print_aligned_lists(self, list_of_lists, title):
        """
        Print a list of lists with each column aligned. Each inner list is joined into a string.
        :param list_of_lists: The input list of lists.
        """
        # Convert all items to strings and determine the maximum width of each column
        str_lists = [[str(item) for item in sublist] for sublist in list_of_lists]
        column_widths = [max(len(item) for item in column) for column in zip(*str_lists)]

        # Print each row with aligned columns
        print(title)
        for sublist in str_lists:
            formatted_row = " | ".join(f"{item:{width}}" for item, width in zip(sublist, column_widths))
            print(formatted_row)
    
    def monitor_ec2(self):

        # if system is idle self-destroy 

        instance_id = self._get_ec2_metadata('instance-id')
        public_ip = self._get_ec2_metadata('public-ipv4')
        instance_type = self._get_ec2_metadata('instance-type')
        ami_id = self._get_ec2_metadata('ami-id')
        reservation_id = self._get_ec2_metadata('reservation-id')
        
        nowstr = datetime.datetime.now().strftime('%H:%M:%S')
        print(f'asm-monitor ({nowstr}): {public_ip} ({instance_id}, {instance_type}, {ami_id}, {reservation_id}) ... ', flush=True)

        if self._monitor_is_idle() or self.monitor_has_instance_failed(instance_id, True):
            # This machine was idle for a long time, destroy it
            print(f'asm-monitor ({nowstr}): Destroying current idling machine {public_ip} ({instance_id}) ...', flush=True)
            if public_ip:
                body_text = "Instance was detected as idle and terminated"
                self.send_email_ses("", "", f'Terminating idle instance {public_ip} ({instance_id})', body_text)
                self.ec2_terminate_instance(public_ip)
                return True 
            else:
                print('Could not retrieve metadata (IP)')
                return False 
            
        current_time = datetime.datetime.now().time()
        start_time = datetime.datetime.strptime("23:00:00", "%H:%M:%S").time()
        end_time = datetime.datetime.strptime("23:59:59", "%H:%M:%S").time()    
        if start_time >= current_time or current_time > end_time:
            # only run cost emails once a day 
            return True 

        monthly_cost, monthly_unit, daily_costs_by_instance, user_monthly_cost, user_monthly_unit, \
            user_daily_cost, user_daily_unit, user_name = self._monitor_get_ec2_costs()
        
        body = []
        body.append(f"{monthly_cost:.2f} {monthly_unit} total account cost for the current month.")
        body.append(f"{user_monthly_cost:.2f} {user_monthly_unit} cost of user {user_name} for the current month.")
        body.append(f"{user_daily_cost:.2f} {user_daily_unit} cost of user {user_name} in the last 24 hours.")
        body.append("Cost for each EC2 instance type in the last 24 hours:")
        for instance_t, (cost, unit) in daily_costs_by_instance.items():
            if instance_t != 'NoInstanceType':
                body.append(f"  {instance_t:12}: ${cost:.2f} {unit}")
        body_text = "\n".join(body)
        self.send_email_ses("", "", f'ASM AWS cost report ({instance_id})', body_text)

    def monitor_has_instance_failed(self, instance_id, print_error):
        """
        Check if the Instance reachability status check has failed for a given EC2 instance.
        """
        #session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        ec2_client = self.awssession.client('ec2')  

        # Fetch the status of the instance
        response = ec2_client.describe_instance_status(InstanceIds=[instance_id])

        # Check if the status check response is available
        if not response['InstanceStatuses']:
            if print_error:
                print(f"No status information found for instance {instance_id}.")
            return True

        # Extract the instance status
        instance_status = response['InstanceStatuses'][0]['InstanceStatus']
        reachability_status = instance_status['Details'][0]['Status']
        if reachability_status == 'impaired' or reachability_status == 'failed':
            if print_error:
                print(f"Instance {instance_id} has failed the reachability status check.")
            return True

        return False


    def _monitor_users_logged_in(self):
        """Check if any users are logged in."""
        try:
            output = subprocess.check_output(['who']).decode('utf-8')
            if output:
                print('asm-monitor: Not idle, logged in:', output)
                return True  # Users are logged in
            return False
        except Exception as e:
            print(f'Other Error: {e}')
            return True
        
    def _monitor_is_idle(self, interval=60, min_idle_cnt=72):

        # each run checks idle time for 60 seconds (interval)
        # if the system has been idle for 72 consecutive runs
        # the fucntion will return idle state after 3 days 
        # if the cron job is running hourly 

        # Constants
        CPU_THRESHOLD = 20  # percent
        NET_READ_THRESHOLD = 1000  # bytes per second
        NET_WRITE_THRESHOLD = 1000  # bytes per second
        DISK_WRITE_THRESHOLD = 100000  # bytes per second
        PROCESS_CPU_THRESHOLD = 10  # percent (for individual processes)
        PROCESS_MEM_THRESHOLD = 10  # percent (for individual processes)
        DISK_WRITE_EXCLUSIONS = ["systemd", "systemd-journald", \
                                "chronyd", "sshd", "auditd" , "agetty"]
    
        # Not idle if any users are logged in 
        if self._monitor_users_logged_in():
            print(f'asm-monitor: Not idle: user(s) logged in')
            #return self._monitor_save_idle_state(False, min_idle_cnt)        
        
        # CPU, Time I/O and Network Activity 
        io_start = psutil.disk_io_counters()
        net_start = psutil.net_io_counters()
        cpu_percent = psutil.cpu_percent(interval=interval)
        io_end = psutil.disk_io_counters()
        net_end = psutil.net_io_counters()

        print(f'asm-monitor: Current CPU% {cpu_percent}')

        # Check CPU Utilization
        if cpu_percent > CPU_THRESHOLD:
            print(f'asm-monitor: Not idle: CPU% {cpu_percent}')
            #return self._monitor_save_idle_state(False, min_idle_cnt)

        # Check I/O Activity
        write_diff = io_end.write_bytes - io_start.write_bytes
        write_per_second = write_diff / interval

        if write_per_second > DISK_WRITE_THRESHOLD:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] in DISK_WRITE_EXCLUSIONS:
                    continue
                try:
                    if proc.io_counters().write_bytes > 0:
                        print(f'asm-monitor:io bytes written: {proc.io_counters().write_bytes}')
                        return self._monitor_save_idle_state(False, min_idle_cnt)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        # Check Network Activity
        bytes_sent_diff = net_end.bytes_sent - net_start.bytes_sent
        bytes_recv_diff = net_end.bytes_recv - net_start.bytes_recv

        bytes_sent_per_second = bytes_sent_diff / interval
        bytes_recv_per_second = bytes_recv_diff / interval

        if bytes_sent_per_second > NET_WRITE_THRESHOLD or \
                            bytes_recv_per_second > NET_READ_THRESHOLD:
            print(f'asm-monitor:net bytes recv: {bytes_recv_per_second}')
            return self._monitor_save_idle_state(False, min_idle_cnt)
            
        # Examine Running Processes for CPU and Memory Usage
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            if proc.info['name'] not in DISK_WRITE_EXCLUSIONS:
                if proc.info['cpu_percent'] > PROCESS_CPU_THRESHOLD:
                    print(f'asm-monitor: Not idle: CPU% {proc.info["cpu_percent"]}')
                    #return False
                # disabled this idle checker 
                #if proc.info['memory_percent'] > PROCESS_MEM_THRESHOLD:
                #    print(f'asm-monitor: Not idle: MEM% {proc.info["memory_percent"]}')
                #    return False

        # Write idle state and read consecutive idle hours
        print(f'asm-monitor: Idle state detected')
        return self._monitor_save_idle_state(True, min_idle_cnt)

    def _monitor_save_idle_state(self, is_system_idle, min_idle_cnt):
        IDLE_STATE_FILE = os.path.join(os.getenv('TMPDIR', '/tmp'), 
                            'asm_idle_state.txt')
        with open(IDLE_STATE_FILE, 'a') as file:
            file.write('1\n' if is_system_idle else '0\n')        
        with open(IDLE_STATE_FILE, 'r') as file:
            states = file.readlines()        
        count = 0
        for state in reversed(states):
            if state.strip() == '1':
                count += 1
            else:
                break
        return count >= min_idle_cnt        

    def _monitor_get_ec2_costs(self, profile=None):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        
        # Set up boto3 client for Cost Explorer
        ce = session.client('ce')
        sts = session.client('sts')

        # Identify current user/account
        identity = sts.get_caller_identity()
        user_arn = identity['Arn']
        # Check if it's the root user
        is_root = ":root" in user_arn

        # Dates for the current month and the last 24 hours
        today = datetime.datetime.today()
        first_day_of_month = datetime.datetime(today.year, today.month, 1).date()
        yesterday = (today - datetime.timedelta(days=1)).date()

        # Fetch EC2 cost of the current month
        monthly_response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': str(first_day_of_month),
                'End': str(today.date())
            },
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Elastic Compute Cloud - Compute']
                }
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
        )
        monthly_cost = float(monthly_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
        monthly_unit = monthly_response['ResultsByTime'][0]['Total']['UnblendedCost']['Unit']

        # If it's the root user, the whole account's costs are assumed to be caused by root.
        if is_root:
            user_name = 'root'
            user_monthly_cost = monthly_cost
            user_monthly_unit = monthly_unit
        else:
            # Assuming a tag `CreatedBy` (change as per your tagging system)
            user_name = user_arn.split('/')[-1]
            user_monthly_response = ce.get_cost_and_usage(
                TimePeriod={
                    'Start': str(first_day_of_month),
                    'End': str(today.date())
                },
                Filter={
                    "And": [
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Compute Cloud - Compute']
                            }
                        },
                        {
                            'Tags': {
                                'Key': 'CreatedBy',
                                'Values': [user_name]
                            }
                        }
                    ]
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
            )
            user_monthly_cost = float(user_monthly_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            user_monthly_unit = user_monthly_response['ResultsByTime'][0]['Total']['UnblendedCost']['Unit']

        # Fetch cost of each EC2 instance type in the last 24 hours
        daily_response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': str(yesterday),
                'End': str(today.date())
            },
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Elastic Compute Cloud - Compute']
                }
            },
            Granularity='DAILY',
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}],
            Metrics=['UnblendedCost'],
        )
        daily_costs_by_instance = {group['Keys'][0]: (float(group['Metrics']['UnblendedCost']['Amount']), group['Metrics']['UnblendedCost']['Unit']) for group in daily_response['ResultsByTime'][0]['Groups']}

        # Fetch cost caused by the current user in the last 24 hours
        if is_root:
            user_daily_cost = sum([cost[0] for cost in daily_costs_by_instance.values()])
            user_daily_unit = monthly_unit  # Using monthly unit since it should be the same for daily
        else:
            user_daily_response = ce.get_cost_and_usage(
                TimePeriod={
                    'Start': str(yesterday),
                    'End': str(today.date())
                },
                Filter={
                    "And": [
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': ['Amazon Elastic Compute Cloud - Compute']
                            }
                        },
                        {
                            'Tags': {
                                'Key': 'CreatedBy',
                                'Values': [user_name]
                            }
                        }
                    ]
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
            )
            user_daily_cost = float(user_daily_response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            user_daily_unit = user_daily_response['ResultsByTime'][0]['Total']['UnblendedCost']['Unit']

        return monthly_cost, monthly_unit, daily_costs_by_instance, user_monthly_cost, \
               user_monthly_unit, user_daily_cost, user_daily_unit, user_name
    

    
class ConfigManager:
    # we write all config entries as files to '~/.config'
    # to make it easier for bash users to read entries 
    # with a simple var=$(cat ~/.config/asm/section/entry)
    # entries can be strings, lists that are written as 
    # multi-line files and dictionaries which are written to json

    def __init__(self, args):
        self.args = args
        self.home_dir = os.path.expanduser('~')
        self.config_root_local = os.path.join(self.home_dir, '.config', 'asm')
        self.config_root = self._get_config_root()
        self.binfolder = self.read('general', 'binfolder').replace(self.home_dir,'~')
        self.binfolderx = os.path.expanduser(self.binfolder)
        self.homepaths = self._get_home_paths()
        self.awscredsfile = os.path.join(self.home_dir, '.aws', 'credentials')
        self.awsconfigfile = os.path.join(self.home_dir, '.aws', 'config')
        self.awsconfigfileshr = os.path.join(self.config_root, 'aws_config')
        self.bucket = self.read('general','bucket')
        self.archiveroot = self.read('general','archiveroot', 'aws')
        self.archivepath = f'{self.bucket}/{self.archiveroot}'
        self.awsprofile = os.getenv('AWS_PROFILE', 'default')
        #print('PROFILE1:', self.awsprofile)
        self.defuser = 'ec2-user'
        profs = self.get_aws_profiles()
        if "aws" in profs:
            self.awsprofile = os.getenv('AWS_PROFILE', 'aws')
        elif "AWS" in profs:
            self.awsprofile = os.getenv('AWS_PROFILE', 'AWS')
        if hasattr(self.args, "awsprofile") and args.awsprofile:
            self.awsprofile = self.args.awsprofile
        
        #print('PROFILE2:', self.awsprofile)
        self.aws_region = self.get_aws_region(self.awsprofile)
        self.envrn = os.environ.copy()
        if not self._set_env_vars(self.awsprofile):
            self.awsprofile = None
        self.ssh_key_name = 'asm-ec2'
        self.scriptname = os.path.basename(__file__)
        #print('PROFILE:', self.awsprofile)
        
    def _set_env_vars(self, profile):
        
        # Read the credentials file
        config = configparser.ConfigParser()
        config.read(self.awscredsfile)
        self.aws_region = self.get_aws_region(profile)

        if not config.has_section(profile):
            if self.args.debug:
                print (f'~/.aws/credentials has no section for profile {profile}')
            return False
        if not config.has_option(profile, 'aws_access_key_id'):
            if self.args.debug:
                print (f'~/.aws/credentials has no entry aws_access_key_id in section/profile {profile}')
            return False
        
        # Set TMPDIR to Store failed EB logs --- too much io and stuff 
        #tmpdir = '/opt/eb/tmp'
        #os.environ['TMPDIR'] = tmpdir
        #self.envrn['TMPDIR'] = tmpdir
        
        # Get the AWS access key and secret key from the specified profile
        aws_access_key_id = config.get(profile, 'aws_access_key_id')
        aws_secret_access_key = config.get(profile, 'aws_secret_access_key')

        # Set the environment variables for creds
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key_id
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
        os.environ['AWS_PROFILE'] = profile
        self.envrn['AWS_ACCESS_KEY_ID'] = aws_access_key_id
        self.envrn['AWS_SECRET_ACCESS_KEY'] = aws_secret_access_key
        self.envrn['AWS_PROFILE'] = profile
        self.envrn['RCLONE_S3_ACCESS_KEY_ID'] = aws_access_key_id
        self.envrn['RCLONE_S3_SECRET_ACCESS_KEY'] = aws_secret_access_key
        os.environ['RCLONE_S3_REQUESTER_PAYS'] = 'true'
        self.envrn['RCLONE_S3_REQUESTER_PAYS'] = 'true'
        
        if profile in ['default', 'AWS', 'aws']:
            # Set the environment variables for AWS 
            self.envrn['RCLONE_S3_PROVIDER'] = 'AWS'
            self.envrn['RCLONE_S3_REGION'] = self.aws_region
            self.envrn['RCLONE_S3_LOCATION_CONSTRAINT'] = self.aws_region
            self.envrn['RCLONE_S3_STORAGE_CLASS'] = self.read('general','s3_storage_class')
            os.environ['RCLONE_S3_STORAGE_CLASS'] = self.read('general','s3_storage_class')
        else:
            prf=self.read('profiles',profile)
            self.envrn['RCLONE_S3_ENV_AUTH'] = 'true'
            self.envrn['RCLONE_S3_PROFILE'] = profile
            if isinstance(prf,dict):  # profile={'name': '', 'provider': '', 'storage_class': ''}
                self.envrn['RCLONE_S3_PROVIDER'] = prf['provider']
                self.envrn['RCLONE_S3_ENDPOINT'] = self._get_aws_s3_session_endpoint_url(profile)
                self.envrn['RCLONE_S3_REGION'] = self.aws_region
                self.envrn['RCLONE_S3_LOCATION_CONSTRAINT'] = self.aws_region
                self.envrn['RCLONE_S3_STORAGE_CLASS'] = prf['storage_class']
                os.environ['RCLONE_S3_STORAGE_CLASS'] = prf['storage_class']

        return True

    def sversion(self, version_str):
        """
        Parse a semantic versioning string into a tuple of integers.
        Args:
        version_str (str): A string representing the version, e.g., "8.2.45".
        Returns:
        tuple: A tuple of integers representing the major, minor, and patch versions.
        """
        parts = version_str.split('.')
        version = []
        for part in parts:
            if part.isdigit():
                version.append(int(part))  # Convert numeric strings to integers
            else:
                version.append(part)  # Keep non-numeric strings as is
        return tuple(version)
    
    def get_os_release_info(self):
        try:
            # Initialize the values
            os_id = ""
            version_id = ""
            # Open the file and read line by line
            with open('/etc/os-release', 'r') as f:
                for line in f:               
                    # Split the line into key and value
                    if line.startswith("ID="):                        
                        os_id = line.strip().split('=')[1].strip('"')
                    elif line.startswith("VERSION_ID="):                    
                        version_id = line.strip().split('=')[1].strip('"')
            os_id = os_id.replace('rocky','rhel')
            if os_id == 'rhel':
                version_id = version_id.split('.')[0]
            return os_id, version_id
        except Exception as e:
            # Return two empty strings in case of an error
            return "", ""
        

    def is_systemd_service_running(self, service_name):
        if not service_name.endswith('.service'):
            service_name += '.service'
        try:
            # Run the systemctl command to check the service status
            result = subprocess.run(['systemctl', 'is-active', service_name], stdout=subprocess.PIPE, text=True)            
            # The output will be 'active' if the service is running
            if result.stdout.strip() == 'active':
                return True
            else:
                return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def _get_home_paths(self):
        path_dirs = os.getenv('PATH','').split(os.pathsep)
        # Filter the directories in the PATH that are inside the home directory
        dirs_inside_home = {
            directory for directory in path_dirs
            if directory.startswith(self.home_dir) and os.path.isdir(directory)
        }
        return sorted(dirs_inside_home, key=len)  

    def _get_config_root(self):
        theroot=self.config_root_local
        rootfile = os.path.join(theroot, 'config_root')
        if os.path.exists(rootfile):
            with open(rootfile, 'r') as myfile:
                theroot = myfile.read().strip()
                if not os.path.isdir(theroot):
                    if not self.ask_yes_no(f'{rootfile} points to a shared config that does not exist. Do you want to configure {theroot} now?'):
                        print (f"Please remove file {rootfile} to continue with a single user config.")
                        sys.exit(1)
                        #raise FileNotFoundError(f'Config root folder "{theroot}" not found. Please remove {rootfile}')
        return theroot

    def _get_section_path(self, section):
        return os.path.join(self.config_root, section)

    def _get_entry_path(self, section, entry):
        if section:
            section_path = self._get_section_path(section)
            return os.path.join(section_path, entry)
        else:
            return os.path.join(self.config_root, entry)

    def _get_os_type(self):
        os_info = {}
        if os.path.isfile("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    key, value = line.strip().split("=", 1)
                    os_info[key] = value.strip('"')
        # Prioritize ID_LIKE over ID
        os_type = os_info.get('ID_LIKE', os_info.get('ID', None))
        # Handle the case where ID_LIKE can contain multiple space-separated strings
        if os_type and ' ' in os_type:
            os_type = os_type.split(' ')[0]  # Get the first 'like' identifier
        return os_type

    def is_ipv4_address(self, string):
        """
        Checks if the given string is a valid IPv4 address using regular expression.
        Returns True if it is, False otherwise.
        """
        pattern = re.compile(r'^(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
        return pattern.match(string) is not None

    def install_os_packages(self, pkg_list, package_skip_set=[]):
        # pkg_list can be a simple list of strings or a list of tuples 
        # if a package has a different name on different OSes
        os_type = self._get_os_type()
        # Determine the appropriate package manager for the detected OS type
        package_manager = None
        if os_type in ['debian', 'ubuntu']:
            package_manager = 'apt'
        elif os_type in ['fedora', 'centos', 'redhat', 'rhel']:
            package_manager = 'dnf'        
        if not package_manager:
            print("Unsupported operating system.")
            return        
        for package_tuple in pkg_list:
            if isinstance(package_tuple, str):
                package_tuple = (package_tuple,)
            installed = False
            for package_name in package_tuple:
                # Check if the package has a known OS-specific suffix
                if package_name in package_skip_set:
                    print(f"Skipping {package_name} because it was already installed.")
                    continue
                if (package_name.endswith('-dev') and os_type in ['debian', 'ubuntu']) or \
                (package_name.endswith('-devel') and os_type in ['fedora', 'centos', 'redhat']):
                    try:
                        print(f"Installing {package_name} with {package_manager}")                    
                        subprocess.run(['sudo', package_manager, 'install', '-y', package_name], check=True)
                        installed = True
                        break
                    except subprocess.CalledProcessError:
                        pass            
            # If none of the packages in the tuple had a suffix, we try to install each until one succeeds
            if not installed:
                for package_name in package_tuple:
                    if package_name in package_skip_set:
                        print(f"Skipping {package_name} because it was already installed.")
                        continue                    
                    try:
                        print(f"Attempting to install {package_name} with {package_manager}")
                        subprocess.run(['sudo', package_manager, 'install', '-y', package_name], check=True)
                        print(f"Installed {package_name} successfully.")
                        break  # Stop trying after the first successful install
                    except subprocess.CalledProcessError:
                        # If the package installation failed, it might be the wrong package for the OS,
                        # so continue trying the next packages in the tuple
                        pass



    def was_file_modified_in_last_24h(self, file_path):
        """
        Check if the file at the given path was modified in the last 24 hours.        
        :param file_path: Path to the file to check.
        :return: True if the file was modified in the last 24 hours, False otherwise.
        """
        try:
            # Get the current time and the last modification time of the file
            current_time = time.time()
            last_modified_time = os.path.getmtime(file_path)

            # Check if the file was modified in the last 24 hours (24 hours = 86400 seconds)
            return (current_time - last_modified_time) < 86400
        except FileNotFoundError:
            # If the file does not exist, return False
            return False
        
    def replace_symlinks_with_realpaths(self, folders):
        cleaned_folders = []
        for folder in folders:
            try:
                # Split the path into its components
                folder = os.path.expanduser(folder)
                #print('expanduser folder:', folder)
                #print('real path:', os.path.realpath(folder))
                cleaned_folders.append(os.path.realpath(folder))
            except Exception as e:
                print(f"Error processing '{folder}': {e}")           
        self.printdbg('cleaned_folders:', cleaned_folders)
        return cleaned_folders            
        
    def printdbg(self, *args, **kwargs):
        # use inspect to get the name of the calling function
        if self.args.debug:
            current_frame = inspect.currentframe()
            calling_function = current_frame.f_back.f_code.co_name 
            print(f' DBG {calling_function}():', args, kwargs)

    def prompt(self, question, defaults=None, type_check=None):
        # Prompts for user input and writes it to config. 
        # defaults are up to 3 pipe separated strings: 
        # if there is only one string this is the default 
        #
        # if there are 2 strings they represent section 
        # and key name of the config entry and if there are 
        # 3 strings the last 2 represent section 
        # and key name of the config file and the first is
        # the default if section and key name are empty
        #
        # if defaults is a python list it will assign a number
        # to each list element and prompt the user for one
        # of the options
        default=''
        section=''
        key=''
        if not question.endswith(':'):
            question += ':'
        question = f"*** {question} ***"
        if isinstance(defaults, list):
            print(question)
            for i, option in enumerate(defaults, 1):
                print(f'  ({i}) {option}')           
            while True:
                selected = input("  Enter the number of your selection: ")
                if selected.isdigit() and 1 <= int(selected) <= len(defaults):
                    return defaults[int(selected) - 1]
                else:
                    print("  Invalid selection. Please enter a number from the list.")
        elif defaults is not None:
            deflist=defaults.split('|')
            if len(deflist) == 3:
                section=deflist[1]
                key=deflist[2]
                default = self.read(section, key)
                if not default:
                    default = deflist[0]
            elif len(deflist) == 2:
                section=deflist[0]
                key=deflist[1]
                default = self.read(section, key)                                
            elif len(deflist) == 1:
                default = deflist[0]
            #if default:
            question += f"\n  [Default: {default}]"
        else:
            question += f"\n  [Default: '']"
        while True:
            #user_input = input(f"\033[93m{question}\033[0m ")
            user_input = input(f"{question} ")
            if not user_input:
                if default is not None:
                    if section:
                        self.write(section,key,default)                    
                    return default
                else:
                    print("Please enter a value.")
            else:
                if type_check == 'number':
                    try:
                        if '.' in user_input:
                            value = float(user_input)
                        else:
                            value = int(user_input)
                        if section:
                            self.write(section,key,value)
                        return value
                    except ValueError:
                        print("Invalid input. Please enter a number.")
                elif type_check == 'string':
                    if not user_input.isnumeric():
                        if section:
                            self.write(section,key,user_input)
                        return user_input
                    else:
                        print("Invalid input. Please enter a string not a number")
                else:
                    if section:
                        self.write(section,key,user_input)
                    return user_input

    def ask_yes_no(self, question, default="yes"):
        valid = {"yes": True, "y": True, "no": False, "n": False}

        if default is None:
            prompt = " [y/n] "
        elif default == "yes":
            prompt = " [Y/n] "
        elif default == "no":
            prompt = " [y/N] "
        else:
            raise ValueError("invalid default answer: '%s'" % default)

        while True:
            print(question + prompt, end="")
            choice = input().lower()
            if default and not choice:
                return valid[default]
            elif choice in valid:
                return valid[choice]
            else:
                print("Please respond with 'yes' or 'no' (or 'y' or 'n').")


    def add_cron_job(self, cmd, minute, hour='*', day_of_month='*', month='*', day_of_week='*'):
        # CURRENTLY INACTIVE
        if not minute:
            print('You must set the minute (1-60) explicily')
            return False 
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            # Dump the current crontab to the temporary file
            try:
                os.system('crontab -l > {}'.format(temp.name))
            except Exception as e:
                print(f"Error: {e}")                

            # Add the new cron job to the temporary file
            cron_time = "{} {} {} {} {}".format(str(minute), hour, day_of_month, month, day_of_week)
            with open(temp.name, 'a') as file:
                file.write('{} {}\n'.format(cron_time, cmd))
            
            # Install the new crontab
            try:            
                os.system('crontab {}'.format(temp.name))
            except Exception as e:
                print(f"Error: {e}")                

            # Clean up by removing the temporary file
            os.unlink(temp.name)

        print("Cron job added!")

    def add_systemd_cron_job(self, cmd, minute, hour='*'):

        # Troubleshoot with: 
        #
        # journalctl -f --user-unit asm-monitor.service
        # journalctl -f --user-unit asm-monitor.timer
        # journalctl --since "5 minutes ago" | grep asm-monitor

        SERVICE_CONTENT = textwrap.dedent(f"""
        [Unit]
        Description=Run ASM-Monitor Cron Job

        [Service]
        Type=simple
        ExecStart={cmd}

        [Install]
        WantedBy=default.target
        """)

        TIMER_CONTENT = textwrap.dedent(f"""
        [Unit]
        Description=Run ASM-Monitor Cron Job hourly

        [Timer]
        Persistent=true
        OnCalendar=*-*-* {hour}:{minute}:00
        #RandomizedDelaySec=300
        #FixedRandomDelay=true
        #OnBootSec=180
        #OnUnitActiveSec=3600
        Unit=asm-monitor.service

        [Install]
        WantedBy=timers.target
        """)

        # Ensure the directory exists
        user_systemd_dir = os.path.expanduser("~/.config/systemd/user/")
        os.makedirs(user_systemd_dir, exist_ok=True)

        SERVICE_PATH = os.path.join(user_systemd_dir, "asm-monitor.service")
        TIMER_PATH = os.path.join(user_systemd_dir, "asm-monitor.timer")

        # Create service and timer files
        with open(SERVICE_PATH, "w") as service_file:
            service_file.write(SERVICE_CONTENT)

        with open(TIMER_PATH, "w") as timer_file:
            timer_file.write(TIMER_CONTENT)

        # Reload systemd and enable/start timer
        try:
            os.chdir(user_systemd_dir)
            os.system("systemctl --user daemon-reload")            
            os.system("systemctl --user enable asm-monitor.service")
            os.system("systemctl --user enable asm-monitor.timer")            
            os.system("systemctl --user start asm-monitor.timer")            
            print("Systemd asm-monitor.timer cron job started!")
        except Exception as e:
            print(f'Could not add systemd scheduler job, Error: {e}')

    def replicate_ini(self, section, src_file, dest_file):

        # copy an ini section from source to destination
        # sync values in dest that do not exist in src back to src
        # best used for sync of AWS profiles.
        # if section==ALL copy all but section called default

        if not os.path.exists(src_file):
            return

        # Create configparser objects
        src_parser = configparser.ConfigParser()
        dest_parser = configparser.ConfigParser()

        # Read source and destination files
        src_parser.read(src_file)
        dest_parser.read(dest_file)

        if section == 'ALL':
            sections = src_parser.sections()
            sections.remove('default') if 'default' in sections else None
        else:
            sections = [section]

        for section in sections:
            # Get the section from source and destination files
            src_section_data = dict(src_parser.items(section))
            dest_section_data = dict(dest_parser.items(section)) if dest_parser.has_section(section) else {}

            # If section does not exist in source or destination file, add it
            if not src_parser.has_section(section):
                src_parser.add_section(section)

            if not dest_parser.has_section(section):
                dest_parser.add_section(section)

            # Write the data into destination file
            for key, val in src_section_data.items():
                dest_parser.set(section, key, val)

            # Write the data into source file
            for key, val in dest_section_data.items():
                if key not in src_section_data:
                    src_parser.set(section, key, val)

        # Save the changes in the destination and source files
        with open(dest_file, 'w') as dest_configfile:
            dest_parser.write(dest_configfile)

        with open(src_file, 'w') as src_configfile:
            src_parser.write(src_configfile)

        if self.args.debug:
            print(f"Ini-section copied from {src_file} to {dest_file}")
            print(f"Missing entries in source from destination copied back to {src_file}")

    def get_aws_profiles(self):
        # get the full list of profiles from ~/.aws/ profile folder
        config = configparser.ConfigParser()        
        # Read the AWS config file ---- optional, we only require a creds file
        try:
            if os.path.exists(self.awsconfigfile):
                config.read(self.awsconfigfile)        
            # Read the AWS credentials file
            if os.path.exists(self.awscredsfile):
                config.read(self.awscredsfile)        
            # Get the list of profiles
            profiles = []
            for section in config.sections():
                profile_name = section.replace("profile ", "") #.replace("default", "default")
                profiles.append(profile_name)
            # convert list to set and back to list to remove dups
            return list(set(profiles))
        except Exception as e:
            print(f"Error: {e}")
            return []

    def create_aws_configs(self,access_key=None, secret_key=None, region=None):

        aws_dir = os.path.join(self.home_dir, ".aws")

        if not os.path.exists(aws_dir):
            os.makedirs(aws_dir, exist_ok=True)

        if not os.path.isfile(self.awsconfigfile):
            if region:
                print(f'\nAWS config file {self.awsconfigfile} does not exist, creating ...')            
                with open(self.awsconfigfile, "w") as config_file:
                    config_file.write("[default]\n")
                    config_file.write(f"region = {region}\n")
                    config_file.write("\n")
                    config_file.write("[profile aws]\n")
                    config_file.write(f"region = {region}\n")

        if not os.path.isfile(self.awscredsfile):
            print(f'\nAWS credentials file {self.awscredsfile} does not exist, creating ...')
            if not access_key: access_key = input("Enter your AWS access key ID: ")
            if not secret_key: secret_key = input("Enter your AWS secret access key: ")            
            with open(self.awscredsfile, "w") as credentials_file:
                credentials_file.write("[default]\n")
                credentials_file.write(f"aws_access_key_id = {access_key}\n")
                credentials_file.write(f"aws_secret_access_key = {secret_key}\n")
                credentials_file.write("\n")
                credentials_file.write("[aws]\n")
                credentials_file.write(f"aws_access_key_id = {access_key}\n")
                credentials_file.write(f"aws_secret_access_key = {secret_key}\n")
            os.chmod(self.awscredsfile, 0o600)

    def set_aws_config(self, profile, key, value, service=''):
        if key == 'endpoint_url': 
            if value.endswith('.amazonaws.com'):
                return False
            else:
                value = f'{value}\nsignature_version = s3v4'
        config = configparser.ConfigParser()
        config.read(os.path.expanduser("~/.aws/config"))
        section=profile
        if profile != 'default':
            section = f'profile {profile}'
        if not config.has_section(section):
            config.add_section(section)
        if service: 
            config.set(section, service, f"\n{key} = {value}\n")
        else:
            config.set(section, key, value)
        with open(os.path.expanduser("~/.aws/config"), 'w') as configfile:
            config.write(configfile)
        return True
    
    def get_aws_s3_endpoint_url(self, profile=None):
        # non boto3 method, use _get_aws_s3_session_endpoint_url instead
        if not profile:
            profile=self.awsprofile
        config = configparser.ConfigParser()
        config.read(os.path.expanduser('~/.aws/config'))
        prof = 'profile ' + profile
        if profile == 'default':
            prof = profile
        try:
            # We use the configparser's interpolation feature here to 
            # flatten the 's3' subsection into the 'profile test' section.
            s3_config_string = config.get(prof, 's3')
            s3_config = configparser.ConfigParser()
            s3_config.read_string("[s3_section]\n" + s3_config_string)
            endpoint_url = s3_config.get('s3_section', 'endpoint_url')
            return endpoint_url
        except (configparser.NoSectionError, configparser.NoOptionError):
            if self.args.debug:
                print("  No endpoint_url found in aws profile:", profile)
            return None
        
    def _get_aws_s3_session_endpoint_url(self, profile=None):
        # retrieve endpoint url through boto API, not configparser
        import botocore.session  # only botocore Session object has attribute 'full_config'
        if not profile:
            profile = self.awsprofile        
        session = botocore.session.Session(profile=profile) if profile else botocore.session.Session()        
        config = session.full_config
        s3_config = config["profiles"][profile].get("s3", {})
        endpoint_url = s3_config.get("endpoint_url", None)
        if self.args.debug:
            print('*** endpoint url ***:', endpoint_url)
        return endpoint_url

    def get_aws_region(self, profile=None):
        try:            
            session = boto3.Session(profile_name=profile) if profile else boto3.Session()
            if self.args.debug:
                print(f'* get_aws_region for profile {profile}:', session.region_name)
            return session.region_name
        except:
            if self.args.debug:
                print(f'  cannot retrieve AWS region for profile {profile}, no valid profile or credentials')
            return ""
            
    def get_domain_name(self):
        try:
            with open('/etc/resolv.conf', 'r') as file:
                content = file.readlines()
        except FileNotFoundError:
            return "mydomain.edu"
        tld = None
        for line in content:
            if line.startswith('search') or line.startswith('domain'):
                tokens = line.split()
                if len(tokens) > 1:
                    tld = tokens.pop()
                    break
        return tld if tld else "mydomain.edu"
    
    def get_time_zone(self):
        current_tz_str = 'America/Los_Angeles'
        try:        
            # Resolve the /etc/localtime symlink
            timezone_path = os.path.realpath("/etc/localtime")
            # Extract the time zone string by stripping off the prefix of the zoneinfo path
            current_tz_str = timezone_path.split("zoneinfo/")[-1]
            #import zoneinfo 
            #current_tz = zoneinfo.ZoneInfo(current_tz_str)\
            #current_time = datetime.datetime.now(current_tz)
        except Exception as e:
            print(f'Error: {e}')
            current_tz_str = 'America/Los_Angeles'
        return current_tz_str
        
    def write(self, section, entry, value):
        entry_path = self._get_entry_path(section, entry)
        os.makedirs(os.path.dirname(entry_path), exist_ok=True)
        if value == '""':
            os.remove(entry_path)
            return
        with open(entry_path, 'w') as entry_file:
            if isinstance(value, list):
                for item in value:
                    entry_file.write(f"{item}\n")
            elif isinstance(value, dict):
                json.dump(value, entry_file, indent=4)
            else:
                entry_file.write(value)

    def read(self, section, entry, default=""):
        entry_path = self._get_entry_path(section, entry)
        if not os.path.exists(entry_path):
            return default
            #raise FileNotFoundError(f'Config entry "{entry}" in section "{section}" not found.')
        with open(entry_path, 'r') as entry_file:
            try:
                return json.load(entry_file)                
            except json.JSONDecodeError:
                pass
            except:
                print('Error in ConfigManager.read(), returning default')
                return default
        with open(entry_path, 'r') as entry_file:
            try:
                content = entry_file.read().splitlines()
                if len(content) == 1:
                    return content[0].strip()
                else:
                    return content
            except:
                print('Error in ConfigManager.read(), returning default')
                return default


    def delete(self, section, entry):
        entry_path = self._get_entry_path(section, entry)
        if not os.path.exists(entry_path):
            raise FileNotFoundError(f'Config entry "{entry}" in section "{section}" not found.')
        os.remove(entry_path)

    def delete_section(self, section):
        section_path = self._get_section_path(section)
        if not os.path.exists(section_path):
            raise FileNotFoundError(f'Config section "{section}" not found.')
        for entry in os.listdir(section_path):
            os.remove(os.path.join(section_path, entry))
        os.rmdir(section_path)

    def move_config(self,cfgfolder):
        if not cfgfolder and self.config_root == self.config_root_local:
                cfgfolder = self.prompt("Please enter the root where folder .config/asm will be created.", 
                                    os.path.expanduser('~'))
        if cfgfolder:
            new_config_root = os.path.join(os.path.expanduser(cfgfolder),'.config','asm')
        else:
            new_config_root = self.config_root
        old_config_root = self.config_root_local
        config_root_file = os.path.join(self.config_root_local,'config_root')
        
        if os.path.exists(config_root_file):
            with open(config_root_file, 'r') as f:
                old_config_root = f.read().strip()
        
        #print(old_config_root,new_config_root)
        if old_config_root == new_config_root:
            return True

        if not os.path.isdir(new_config_root):
            if os.path.isdir(old_config_root):
                shutil.move(old_config_root,new_config_root) 
                if os.path.isdir(old_config_root):
                    try:
                        os.rmdir(old_config_root)
                    except:
                        pass
                print(f'  ASM config moved to "{new_config_root}"\n')
            os.makedirs(new_config_root,exist_ok=True)
            if os.path.exists(self.awsconfigfile):
                self.replicate_ini('ALL',self.awsconfigfile,os.path.join(new_config_root,'aws_config'))
                print(f'  ~/.aws/config replicated to "{new_config_root}/aws_config"\n')  

        self.config_root = new_config_root

        os.makedirs(old_config_root,exist_ok=True)
        with open(config_root_file, 'w') as f:
            f.write(self.config_root)
            print(f'  Switched configuration path to "{self.config_root}"')
        return True
    
    def wait_for_ssh_ready(self, hostname, ip, port=22, dnstimeout=33, timeout=60):
        start_time = time.time()
        time.sleep(1)
        while time.time() - start_time < timeout:
            # if time.time() - start_time >= dnstimeout:
            #     hostname = ip
            #     print(f" Waiting for host to be ready: {hostname} ... ")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)  # Set a timeout on the socket operations            
            try:
                result = s.connect_ex((hostname, port))
            except socket.gaierror:
                print(f" Waiting for host name to populate in DNS: {hostname} ...")
                result = 1 
            if result == 0:
                s.close()
                return True
            else:
                time.sleep(3)  # Wait for 5 seconds before retrying
                s.close()
        print("Timeout reached without SSH server being ready.")
        return False
    
    def parse_version_string(self, thestring):
        """
        Parse the string to extract everything up to and including the last numeric character
        in the first sequence of numeric characters. Dots are treated as numeric characters.
        """

        thestring = thestring.replace('-9-EC2-Base-','-')
        numeric_found = False
        last_numeric_index = -1
        last_slash_before_numeric = -1

        for i, char in enumerate(thestring):
            if char.isdigit() or char == '.':
                if not numeric_found:
                    # Check for '/' before the first numeric character
                    last_slash_before_numeric = thestring.rfind('/', 0, i)
                numeric_found = True
                last_numeric_index = i
            elif numeric_found:
                # Break as soon as a non-numeric character is found after the first sequence of numeric characters
                break

        # Slice the string to start from after the last '/' before the first numeric sequence
        start_index = last_slash_before_numeric + 1 if last_slash_before_numeric != -1 else 0
        return thestring[start_index:last_numeric_index + 1] if numeric_found else ""

    def _walker(self, top, skipdirs=['.snapshot', '__archive__']):
        """ returns subset of os.walk  """
        for root, dirs, files in os.walk(top,topdown=True,onerror=self._walkerr): 
            for skipdir in skipdirs:
                if skipdir in dirs:
                    dirs.remove(skipdir)  # don't visit this directory 
            yield root, dirs, files 

    def _walkerr(self, oserr):    
        sys.stderr.write(str(oserr))
        sys.stderr.write('\n')
        return 0

    def copy_compiled_binary_from_github(self,user,repo,compilecmd,binary,targetfolder):
        tarball_url = f"https://github.com/{user}/{repo}/archive/refs/heads/main.tar.gz"
        response = requests.get(tarball_url, stream=True, allow_redirects=True)
        response.raise_for_status()
        with tempfile.TemporaryDirectory() as tmpdirname:
            reposfolder=os.path.join(tmpdirname,  f"{repo}-main")
            with tarfile.open(fileobj=response.raw, mode="r|gz") as tar:
                tar.extractall(path=tmpdirname)
                reposfolder=os.path.join(tmpdirname,  f"{repo}-main")
                os.chdir(reposfolder)
                result = subprocess.run(compilecmd, shell=True)
                if result.returncode == 0:
                    print(f"Compilation successful: {compilecmd}")
                    shutil.copy2(binary, targetfolder, follow_symlinks=True)
                    if not os.path.exists(os.path.join(targetfolder, binary)):
                        print(f'Failed copying {binary} to {targetfolder}')                
                else:
                    print(f"Compilation failed: {compilecmd}")

    def copy_binary_from_zip_url(self,zipurl,binary,subwildcard,targetfolder):
        with tempfile.TemporaryDirectory() as tmpdirname:
            zip_file = os.path.join(tmpdirname,  "download.zip")
            response = requests.get(zipurl, verify=False, allow_redirects=True)
            with open(zip_file, 'wb') as f:
                f.write(response.content)
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(tmpdirname)
            binpath = glob.glob(f'{tmpdirname}{subwildcard}{binary}')[0]
            shutil.copy2(binpath, targetfolder, follow_symlinks=True)
            if os.path.exists(os.path.join(targetfolder, binary)):
                os.chmod(os.path.join(targetfolder, binary), 0o775)
            else:    
                print(f'Failed copying {binary} to {targetfolder}')

def parse_arguments():
    """
    Gather command-line arguments.
    """
    parser = argparse.ArgumentParser(prog='asm ',
        description='ASM is a script that creates Linux machines (EC2 Instances on Amazon) ' + \
                    'with good defaults. It will download lots of precompiled software ')
    parser.add_argument( '--debug', '-d', dest='debug', action='store_true', default=False,
        help="verbose output for all commands")
    parser.add_argument('--profile', '-p', dest='awsprofile', action='store', default='', metavar='<aws-profile>',
        help='which AWS profile in ~/.aws/ should be used. default="aws"')
    parser.add_argument('--no-checksums', '-u', dest='nochecksums', action='store_true', default=False,
        help="Use --size-only instead of --checksum when using rclone with S3.")      
    parser.add_argument('--version', '-v', dest='version', action='store_true', default=False, 
        help='print ASM and Python version info')
    
    subparsers = parser.add_subparsers(dest="subcmd", help='sub-command help')

    # ***
    parser_config = subparsers.add_parser('config', aliases=['cnf'], 
        help=textwrap.dedent(f'''            
            You will need to answer just a few questions about your cloud setup.
        '''), formatter_class=argparse.RawTextHelpFormatter)
    parser_config.add_argument( '--list', '-l', dest='list', action='store_true', default=False,
        help="List available CPU/GPU types and supported prefixes (OS/CPU)")           
    parser_config.add_argument( '--monitor', '-m', dest='monitor', action='store', default='',                               
        metavar='<email@address.org>', help='setup asm as a monitoring cronjob ' +
        'on an ec2 instance and notify an email address')
    parser_config.add_argument( '--dns-cleanup', '-d', dest='dnscleanup', action='store_true', default=False,
        help="Clean unused A records from Route53 DNS")    
    parser_config.add_argument( '--test', '-t', dest='test', action='store_true', default=False,
        help="Test option simply for software debugging")
    parser_config.add_argument('--os', '-o', dest='os', action='store', default="amazon",
        help='build operating system, default=amazon (which is an optimized fedora) ' + 
        'valid choices are: amazon, rhel, ubuntu and any AMI name including wilcards *')    
    parser_config.add_argument('--cpu-type', '-c', dest='cputype', action='store', default="graviton-3", 
        metavar='<cpu-type>', help='run config --list to see available CPU types. (e.g graviton-3)')    
        
    # ***
    parser_launch = subparsers.add_parser('launch', aliases=['lau'],
        help=textwrap.dedent(f'''
            Launch EC2 instance with good default settings 
        '''), formatter_class=argparse.RawTextHelpFormatter) 
    parser_launch.add_argument('--cpu-type', '-c', dest='cputype', action='store', default="graviton-4", 
        metavar='<cpu-type>', help='run config --list to see available CPU types. (e.g graviton-4)')
    parser_launch.add_argument('--os', '-o', dest='os', action='store', default="amazon",
        help='build operating system, default=amazon (which is an optimized fedora) ' + 
        'valid choices are: amazon, rhel, ubuntu and any AMI name including wilcards *')
    parser_launch.add_argument('--vcpus', '-v', dest='vcpus', type=int, action='store', default=2, metavar='<number-of-vcpus>',
        help='Number of vcpus to be allocated for compilations on the target machine. (default=2) ' +
        'On x86-64 there are 2 vcpus per core and on Graviton (Arm) there is one core per vcpu')
    parser_launch.add_argument('--gpu-type', '-g', dest='gputype', action='store', default="", metavar='<gpu-type>',
        help='run --list to see available GPU types')       
    parser_launch.add_argument('--mem', '-m', dest='mem', type=int, action='store', default=8, metavar='<memory-size-gb>',
        help='GB Memory allocated to instance  (default=8)')
    parser_launch.add_argument('--disk', '-d', dest='disk', type=int, action='store', default=225, metavar='<disk-size-gb>',
        help='Add an EBS disk to the instance and mount it to /opt (default=225 GB')
    parser_launch.add_argument('--instance-type', '-t', dest='instancetype', action='store', default="", metavar='<aws.instance>',
        help='The EC2 instance type is auto-selected, but you can pick any other type here')    
    parser_launch.add_argument('--az', '-z', dest='az', action='store', default="",
        help='Enforce the availability zone, e.g. us-west-2a')    
    parser_launch.add_argument('--on-demand', '-w', dest='ondemand', action='store_true', default=False,
        help="Enforce on-demand instance instead of using the default spot instance.")
    # parser_launch.add_argument('--keep-running', '-u', dest='keeprunning', action='store_true', default=False,
    #     help="Do not shut down EC2 instance after builds are done, keep it running.")
    parser_launch.add_argument('--monitor', '-n', dest='monitor', action='store_true', default=False,
        help="Monitor EC2 server for cost and idle time.")
    parser_launch.add_argument('--bootstrap', '-b', dest='bootstrap', action='store_true', default=False,
        help="bootstrap software on the current system instead of launching a new EC2 instance.")      
    parser_launch.add_argument('--force-sshkey', '-r', dest='forcesshkey', action='store_true', default=False,
        help='This option will overwrite the ssh key pair in AWS with a new one and download it.')    
    parser_launch.add_argument('--skip-download', '-s', dest='skipdownload', action='store_true', default=False,
        help='Skip downloading the built scientific packages and lmod modules to /opt/eb')
    parser_launch.add_argument('--download-target', '-l',dest='downloadtarget', action='store', default='/opt/eb',
        metavar='<target_folder>', help='Download software to other folder than default (/opt/eb)')
   
    # # ***
    # parser_download = subparsers.add_parser('download', aliases=['dld'],
    #     help=textwrap.dedent(f'''
    #         Download built eb packages and lmod modules to /opt/eb
    #     '''), formatter_class=argparse.RawTextHelpFormatter)      
    # parser_download.add_argument('--cpu-type', '-c', dest='cputype', action='store', default="",
    #     help='run --list to see available CPU types, use --prefix to select OS-version_cpu-type')
    # parser_download.add_argument('--prefix', '-p', dest='prefix', action='store', default='', 
    #     metavar='<s3_prefix>', help='your prefix, e.g. amzn-2023_graviton-3, ubuntu-22.04_xeon-gen-1')
    # parser_download.add_argument('--vcpus', '-v', dest='vcpus', type=int, action='store', default=4, 
    #     help='Number of vcpus to be allocated for compilations on the target machine. (default=4) ' +
    #     'On x86-64 there are 2 vcpus per core and on Graviton (Arm) there is one core per vcpu')    
    # parser_download.add_argument( '--with-source', '-s', dest='withsource', action='store_true', default=False,
    #     help="Also download the source packages")
    # parser_download.add_argument('target', action='store', nargs='?', default='/opt/eb',
    #     metavar='<target_folder>', help='Download to other folder than default')    

    # # ***
    # parser_buildstatus = subparsers.add_parser('buildstatus', aliases=['sta'],
    #     help=textwrap.dedent(f'''
    #         Show stats on eb-build-status.json in this S3 folder (including prefix), e.g.
    #         'amzn-2023_graviton-3', 'amzn-2023_epyc-gen-4', 'amzn-2023_xeon-gen-4'
    #         rhel-9_xeon-gen-1 or ubuntu-22.04_xeon-gen-1.
    #     '''), formatter_class=argparse.RawTextHelpFormatter) 
    # parser_buildstatus.add_argument('prefix', action='store', default='', 
    #     metavar='<s3_prefix>', help='your prefix, e.g. amzn-2023_graviton-3')    

    # ***
    parser_ssh = subparsers.add_parser('ssh', aliases=['scp'],
        help=textwrap.dedent(f'''
            Login to an AWS EC2 build instance 
        '''), formatter_class=argparse.RawTextHelpFormatter)
    parser_ssh.add_argument( '--list', '-l', dest='list', action='store_true', default=False,
        help="List running ASM EC2 instances")               
    parser_ssh.add_argument('--terminate', '-t', dest='terminate', action='store', default='', 
        metavar='<hostname>', help='Terminate EC2 instance with this public IP Address.')    
    parser_ssh.add_argument('--add-key', '-a', dest='addkey', action='store', default='', 
        metavar='<private-ssh-key.pem>', help='Generate a pub key and add it to a remote authorized_keys file.') 
    parser_ssh.add_argument('sshargs', action='store', default=[], nargs='*',
        help='multiple arguments to ssh/scp such as hostname or user@hostname oder folder' +
               '')

    if len(sys.argv) == 1:
        parser.print_help(sys.stdout)               

    return parser.parse_args()

if __name__ == "__main__":
    if not sys.platform.startswith('linux'):
        print('This software currently only runs on Linux x64')
        sys.exit(1)
    try:
        args = parse_arguments()
        if main():
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nExit !')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
