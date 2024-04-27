# ASM (Amazon Science Machine)

ASM (Amazon Science Machine) launches an AWS EC2 Linux machine with pre-compiled scientific software and good defaults for Scientists. You can choose from the latest Amazon Linux, Redhat Enterprise (Rocky) or Ubuntu LTS. Your SSH keys will be generated automatically and if your sysadmin has setup a DNS zone you will also get a DNS name. You will be prompted for a storage location (S3 bucket) which will be mounted at /mnt/[bucket-name] as a quasi-filesystem using rclone

Install: 
```
curl -s https://raw.githubusercontent.com/dirkpetersen/asm/main/install.sh | bash
```
Launch: 

[![asciicast](https://asciinema.org/a/vvpaBisB9HGFtE13pgHvLL8xB.svg)](https://asciinema.org/a/vvpaBisB9HGFtE13pgHvLL8xB)





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
