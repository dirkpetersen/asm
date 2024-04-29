# ASM (Amazon Science Machine)

ASM (Amazon Science Machine) launches an AWS EC2 Linux machine with pre-compiled scientific software and good defaults for scientists. You can choose from the latest Amazon Linux, Redhat Enterprise (Rocky) or Ubuntu LTS. Your SSH keys will be generated automatically and if your sysadmin has setup a DNS zone you will also get a DNS name. You will be prompted for a storage location (S3 bucket) which will be mounted at /mnt/[bucket-name] as a quasi-filesystem using rclone. There is also a test file system using JuiceFS 

Install: 
```
curl -s https://raw.githubusercontent.com/dirkpetersen/asm/main/install.sh | bash
```
Config (for example setup the S3 bucket to use):
```
asm config 
```
Launch: 
[![asciicast](https://asciinema.org/a/vvpaBisB9HGFtE13pgHvLL8xB.svg)](https://asciinema.org/a/vvpaBisB9HGFtE13pgHvLL8xB)


## Config details

```
dp@grammy:~$ asm config
 Installing rclone ... please wait ... Done!

*** Asking a few questions ***
*** For most you can just hit <Enter> to accept the default. ***

*** Enter your email address: ***
  [Default: dp@gmail.com]

*** Please confirm/edit the standard hostname prefix. Use something short like your initials or first name. All machines will have a hostname with this prefix followed by a number : ***
  [Default: dp]

*** Please confirm/edit S3 bucket name to be created in all used profiles.: ***
  [Default: asm-dp]
*** Please confirm/edit the root path inside your S3 bucket: ***
  [Default: dp]

  Verify that bucket 'asm-dp' is configured ...
Done!
```


## Errors

expired SSO creds 

```
 ./asm launch
Error retrieving instance types: Error when retrieving token from sso: Token has expired and refresh failed
No instances match the criteria. is the cheapest spot instance with at least 4 vcpus / 8 GB mem
Other Error: Error when retrieving token from sso: Token has expired and refresh failed
Other Error: Error when retrieving token from sso: Token has expired and refresh failed
Other Error: Error when retrieving token from sso: Token has expired and refresh failed
```
