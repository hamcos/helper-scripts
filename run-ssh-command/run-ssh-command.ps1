#requires -version 2
# Help {{{1
<#
.SYNOPSIS
    Execute command via SSH
.DESCRIPTION
    The script handles credentials and logging for you and allows to easily run
    SSH commands using the Posh-SSH PowerShell module.
.PARAMETER HostName
    Required. The hostname of the remote host on which a SSH server is running.
.PARAMETER UserName
    Optional. Username, defaults "apc".
.PARAMETER Command
    Required. The command to run on the remote host.
.PARAMETER Credential
    Optional. Allows to pass an already existing objected credential object.
.INPUTS
    None
.OUTPUTS
    Logs
.NOTES
    @author Robin Schneider <robin.schneider@hamcos.de>
    @company hamcos IT Service GmbH https://www.hamcos.de
    @license AGPLv3 <https://www.gnu.org/licenses/agpl-3.0.html>

    Copyright (C) 2017 Robin Schneider <robin.schneider@hamcos.de>
    Copyright (C) 2017 hamcos IT Service GmbH https://www.hamcos.de

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, version 3 of the
    License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

    This script depends on: https://github.com/darkoperator/Posh-SSH
    Get the current version at: https://github.com/hamcos/helper-scripts/tree/master/run-ssh-command

.EXAMPLE
    ./run-ssh-command.ps1 -HostName $fqdn -Command "uptime"
#>

# https://stackoverflow.com/questions/7160443/how-to-make-parameters-mandatory-in-powershell
# Did not work.

Param(
    [string]$HostName,
    [string]$UserName="apc",
    [string]$Command,
    $CredentialsPath="C:\batch\creds",
    $Credential
)

# Functions {{{1

Function LogWrite
{
   Param ([string]$logstring)

   $sLogPath = "C:/Windows/Temp"
   $sLogName = "run-ssh-command.log"
   $sLogFile = Join-Path -Path $sLogPath -ChildPath $sLogName

   $timestamp_rfc3339 = Get-Date -format "yyyy-MM-dd HH:mm:ss"
   Add-content $sLogFile -value ("{0}: {1}" -f $timestamp_rfc3339, $logstring)
}

# Initializations {{{1

# Declarations {{{1

$sScriptVersion = "0.1.0"

# Execution {{{1

if (!($HostName)) {
    Write-Host -Fore Red "Argument missing: -HostName"
    Exit
}
if (!($Command)) {
    Write-Host -Fore Red "Argument missing: -Command"
    Exit
}

if (!($Credential)) {
    $PasswordFile = Join-Path -Path $CredentialsPath -ChildPath ($CredentialsPath = '{0}.pw' -f $HostName)
    $Credential = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $UserName, (Get-Content $PasswordFile | ConvertTo-SecureString)

    # $Password = $insert_pw_here | ConvertTo-SecureString -AsPlainText -Force
    # $Password | ConvertFrom-SecureString | Out-File $File
}

LogWrite ("Running run-ssh-command, host: {0}, command: {1}" -f $HostName, $Command)

Import-Module -Name posh-ssh

$session = New-SSHSession -ComputerName $HostName -Credential $Credential
$stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)

sleep -m 500
## Read in void context. We don’t need login banner and MOTD.
$stream.Read() | out-null

$stream.Write($Command + "
")
sleep -m 200
$output = $stream.Read()
# Remove what we just entered and which the remote shell happily returned to us:
$output = $output -replace ("^" + $Command), ""
# Remove the prompt returned by the remote shell after the given command terminated:
$output = $output -replace ".+>$", ""
LogWrite ("Remote SSH session returned: {0}" -f $output.Trim())

$stream.Write("quit
")
