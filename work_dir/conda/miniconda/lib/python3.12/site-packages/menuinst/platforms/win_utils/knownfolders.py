"""
This code obtained from
https://gist.github.com/mkropat/7550097

The MIT License (MIT)

Copyright (c) 2014 Michael Kropat

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import ctypes
import os
from ctypes import windll, wintypes
from logging import getLogger
from pathlib import Path
from typing import List
from uuid import UUID

logger = getLogger(__name__)


class GUID(ctypes.Structure):  # [1]
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]

    def __init__(self, uuid_):
        ctypes.Structure.__init__(self)
        self.Data1, self.Data2, self.Data3, self.Data4[0], self.Data4[1], rest = uuid_.fields
        for i in range(2, 8):
            self.Data4[i] = rest >> (8 - i - 1) * 8 & 0xFF


class FOLDERID:  # [2]
    AccountPictures = UUID('{008ca0b1-55b4-4c56-b8a8-4de4b299d3be}')
    AdminTools = UUID('{724EF170-A42D-4FEF-9F26-B60E846FBA4F}')
    ApplicationShortcuts = UUID('{A3918781-E5F2-4890-B3D9-A7E54332328C}')
    CameraRoll = UUID('{AB5FB87B-7CE2-4F83-915D-550846C9537B}')
    CDBurning = UUID('{9E52AB10-F80D-49DF-ACB8-4330F5687855}')
    CommonAdminTools = UUID('{D0384E7D-BAC3-4797-8F14-CBA229B392B5}')
    CommonOEMLinks = UUID('{C1BAE2D0-10DF-4334-BEDD-7AA20B227A9D}')
    CommonPrograms = UUID('{0139D44E-6AFE-49F2-8690-3DAFCAE6FFB8}')
    CommonStartMenu = UUID('{A4115719-D62E-491D-AA7C-E74B8BE3B067}')
    CommonStartup = UUID('{82A5EA35-D9CD-47C5-9629-E15D2F714E6E}')
    CommonTemplates = UUID('{B94237E7-57AC-4347-9151-B08C6C32D1F7}')
    Contacts = UUID('{56784854-C6CB-462b-8169-88E350ACB882}')
    Cookies = UUID('{2B0F765D-C0E9-4171-908E-08A611B84FF6}')
    Desktop = UUID('{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}')
    DeviceMetadataStore = UUID('{5CE4A5E9-E4EB-479D-B89F-130C02886155}')
    Documents = UUID('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}')
    DocumentsLibrary = UUID('{7B0DB17D-9CD2-4A93-9733-46CC89022E7C}')
    Downloads = UUID('{374DE290-123F-4565-9164-39C4925E467B}')
    Favorites = UUID('{1777F761-68AD-4D8A-87BD-30B759FA33DD}')
    Fonts = UUID('{FD228CB7-AE11-4AE3-864C-16F3910AB8FE}')
    GameTasks = UUID('{054FAE61-4DD8-4787-80B6-090220C4B700}')
    History = UUID('{D9DC8A3B-B784-432E-A781-5A1130A75963}')
    ImplicitAppShortcuts = UUID('{BCB5256F-79F6-4CEE-B725-DC34E402FD46}')
    InternetCache = UUID('{352481E8-33BE-4251-BA85-6007CAEDCF9D}')
    Libraries = UUID('{1B3EA5DC-B587-4786-B4EF-BD1DC332AEAE}')
    Links = UUID('{bfb9d5e0-c6a9-404c-b2b2-ae6db6af4968}')
    LocalAppData = UUID('{F1B32785-6FBA-4FCF-9D55-7B8E7F157091}')
    LocalAppDataLow = UUID('{A520A1A4-1780-4FF6-BD18-167343C5AF16}')
    LocalizedResourcesDir = UUID('{2A00375E-224C-49DE-B8D1-440DF7EF3DDC}')
    Music = UUID('{4BD8D571-6D19-48D3-BE97-422220080E43}')
    MusicLibrary = UUID('{2112AB0A-C86A-4FFE-A368-0DE96E47012E}')
    NetHood = UUID('{C5ABBF53-E17F-4121-8900-86626FC2C973}')
    OriginalImages = UUID('{2C36C0AA-5812-4b87-BFD0-4CD0DFB19B39}')
    PhotoAlbums = UUID('{69D2CF90-FC33-4FB7-9A0C-EBB0F0FCB43C}')
    PicturesLibrary = UUID('{A990AE9F-A03B-4E80-94BC-9912D7504104}')
    Pictures = UUID('{33E28130-4E1E-4676-835A-98395C3BC3BB}')
    Playlists = UUID('{DE92C1C7-837F-4F69-A3BB-86E631204A23}')
    PrintHood = UUID('{9274BD8D-CFD1-41C3-B35E-B13F55A758F4}')
    Profile = UUID('{5E6C858F-0E22-4760-9AFE-EA3317B67173}')
    ProgramData = UUID('{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}')
    ProgramFiles = UUID('{905e63b6-c1bf-494e-b29c-65b732d3d21a}')
    ProgramFilesX64 = UUID('{6D809377-6AF0-444b-8957-A3773F02200E}')
    ProgramFilesX86 = UUID('{7C5A40EF-A0FB-4BFC-874A-C0F2E0B9FA8E}')
    ProgramFilesCommon = UUID('{F7F1ED05-9F6D-47A2-AAAE-29D317C6F066}')
    ProgramFilesCommonX64 = UUID('{6365D5A7-0F0D-45E5-87F6-0DA56B6A4F7D}')
    ProgramFilesCommonX86 = UUID('{DE974D24-D9C6-4D3E-BF91-F4455120B917}')
    Programs = UUID('{A77F5D77-2E2B-44C3-A6A2-ABA601054A51}')
    Public = UUID('{DFDF76A2-C82A-4D63-906A-5644AC457385}')
    PublicDesktop = UUID('{C4AA340D-F20F-4863-AFEF-F87EF2E6BA25}')
    PublicDocuments = UUID('{ED4824AF-DCE4-45A8-81E2-FC7965083634}')
    PublicDownloads = UUID('{3D644C9B-1FB8-4f30-9B45-F670235F79C0}')
    PublicGameTasks = UUID('{DEBF2536-E1A8-4c59-B6A2-414586476AEA}')
    PublicLibraries = UUID('{48DAF80B-E6CF-4F4E-B800-0E69D84EE384}')
    PublicMusic = UUID('{3214FAB5-9757-4298-BB61-92A9DEAA44FF}')
    PublicPictures = UUID('{B6EBFB86-6907-413C-9AF7-4FC2ABF07CC5}')
    PublicRingtones = UUID('{E555AB60-153B-4D17-9F04-A5FE99FC15EC}')
    PublicUserTiles = UUID('{0482af6c-08f1-4c34-8c90-e17ec98b1e17}')
    PublicVideos = UUID('{2400183A-6185-49FB-A2D8-4A392A602BA3}')
    QuickLaunch = UUID('{52a4f021-7b75-48a9-9f6b-4b87a210bc8f}')
    Recent = UUID('{AE50C081-EBD2-438A-8655-8A092E34987A}')
    RecordedTVLibrary = UUID('{1A6FDBA2-F42D-4358-A798-B74D745926C5}')
    ResourceDir = UUID('{8AD10C31-2ADB-4296-A8F7-E4701232C972}')
    Ringtones = UUID('{C870044B-F49E-4126-A9C3-B52A1FF411E8}')
    RoamingAppData = UUID('{3EB685DB-65F9-4CF6-A03A-E3EF65729F3D}')
    RoamedTileImages = UUID('{AAA8D5A5-F1D6-4259-BAA8-78E7EF60835E}')
    RoamingTiles = UUID('{00BCFC5A-ED94-4e48-96A1-3F6217F21990}')
    SampleMusic = UUID('{B250C668-F57D-4EE1-A63C-290EE7D1AA1F}')
    SamplePictures = UUID('{C4900540-2379-4C75-844B-64E6FAF8716B}')
    SamplePlaylists = UUID('{15CA69B3-30EE-49C1-ACE1-6B5EC372AFB5}')
    SampleVideos = UUID('{859EAD94-2E85-48AD-A71A-0969CB56A6CD}')
    SavedGames = UUID('{4C5C32FF-BB9D-43b0-B5B4-2D72E54EAAA4}')
    SavedSearches = UUID('{7d1d3a04-debb-4115-95cf-2f29da2920da}')
    Screenshots = UUID('{b7bede81-df94-4682-a7d8-57a52620b86f}')
    SearchHistory = UUID('{0D4C3DB6-03A3-462F-A0E6-08924C41B5D4}')
    SearchTemplates = UUID('{7E636BFE-DFA9-4D5E-B456-D7B39851D8A9}')
    SendTo = UUID('{8983036C-27C0-404B-8F08-102D10DCFD74}')
    SidebarDefaultParts = UUID('{7B396E54-9EC5-4300-BE0A-2482EBAE1A26}')
    SidebarParts = UUID('{A75D362E-50FC-4fb7-AC2C-A8BEAA314493}')
    SkyDrive = UUID('{A52BBA46-E9E1-435f-B3D9-28DAA648C0F6}')
    SkyDriveCameraRoll = UUID('{767E6811-49CB-4273-87C2-20F355E1085B}')
    SkyDriveDocuments = UUID('{24D89E24-2F19-4534-9DDE-6A6671FBB8FE}')
    SkyDrivePictures = UUID('{339719B5-8C47-4894-94C2-D8F77ADD44A6}')
    StartMenu = UUID('{625B53C3-AB48-4EC1-BA1F-A1EF4146FC19}')
    Startup = UUID('{B97D20BB-F46A-4C97-BA10-5E3608430854}')
    System = UUID('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}')
    SystemX86 = UUID('{D65231B0-B2F1-4857-A4CE-A8E7C6EA7D27}')
    Templates = UUID('{A63293E8-664E-48DB-A079-DF759E0509F7}')
    UserPinned = UUID('{9E3995AB-1F9C-4F13-B827-48B24B6C7174}')
    UserProfiles = UUID('{0762D272-C50A-4BB0-A382-697DCD729B80}')
    UserProgramFiles = UUID('{5CD7AEE2-2219-4A67-B85D-6C9CE15660CB}')
    UserProgramFilesCommon = UUID('{BCBD3057-CA5C-4622-B42D-BC56DB0AE516}')
    Videos = UUID('{18989B1D-99B5-455B-841C-AB7C74E4DDFC}')
    VideosLibrary = UUID('{491E922F-5643-4AF4-A7EB-4E7A138D8174}')
    Windows = UUID('{F38BF404-1D43-42F2-9305-67DE0B28FC23}')


class UserHandle:  # [3]
    current = wintypes.HANDLE(0)
    common = wintypes.HANDLE(-1)


_CoTaskMemFree = windll.ole32.CoTaskMemFree  # [4]
_CoTaskMemFree.restype = None
_CoTaskMemFree.argtypes = [ctypes.c_void_p]

_SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath  # [5] [3]
_SHGetKnownFolderPath.argtypes = [
    ctypes.POINTER(GUID),
    wintypes.DWORD,
    wintypes.HANDLE,
    ctypes.POINTER(ctypes.c_wchar_p),
]

'''
# Please keep this code around in-case we need to debug tricky installations
# http://stackoverflow.com/a/15016751/3257826 - needs pywin32
import pythoncom
from win32com.shell import shell, shellcon
from win32com import storagecon
import os
kfm = pythoncom.CoCreateInstance(shell.CLSID_KnownFolderManager, None,
        pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IKnownFolderManager)
dir(kfm)
folders = kfm.GetFolderIds()
for folder in folders:
    print(folder)
try:
    docs_folder = kfm.GetFolder(shell.FOLDERID_Documents)
    docs_path = docs_folder.GetPath()
    print(docs_path)
except:
    pass
'''


class PathNotFoundException(Exception):
    pass


class PathNotVerifiableException(Exception):
    pass


def get_path(folderid, user_handle=UserHandle.common):
    fid = GUID(folderid)
    pPath = ctypes.c_wchar_p()
    pPathUnverified = ctypes.c_wchar_p()
    S_OK = 0
    KF_FLAG_DONT_VERIFY = 0x00004000
    result = _SHGetKnownFolderPath(
        ctypes.byref(fid), KF_FLAG_DONT_VERIFY, user_handle, ctypes.byref(pPathUnverified)
    )
    exception = None
    if result != S_OK:
        exception = PathNotFoundException()
    else:
        result = _SHGetKnownFolderPath(ctypes.byref(fid), 0, user_handle, ctypes.byref(pPath))
        if result != S_OK:
            exception = PathNotVerifiableException()
            pPath = pPathUnverified
        else:
            _CoTaskMemFree(pPathUnverified)

    path = pPath.value
    _CoTaskMemFree(pPath)
    return (path, exception)


def get_folder_path(folder_id, user=None):
    if not user:
        user = UserHandle.current
    # We may want to support modifying the 'Default' user here too for SCCM-based installations.
    # New users created on the machine have their folders created by copying those of 'Default'.
    return get_path(folder_id, user)


# [1] http://msdn.microsoft.com/en-us/library/windows/desktop/aa373931.aspx
# [2] http://msdn.microsoft.com/en-us/library/windows/desktop/dd378457.aspx
# [3] http://msdn.microsoft.com/en-us/library/windows/desktop/bb762188.aspx
# [4] http://msdn.microsoft.com/en-us/library/windows/desktop/ms680722.aspx
# [5] http://www.themacaque.com/?p=954

# jaimergp: The code below was copied from menuinst.win32, 1.4.19
# module: menuinst/win32.py -
#    https://github.com/conda/menuinst/blob/e17afafd/menuinst/win32.py#L40-L102
# ----
# When running as 'nt authority/system' as sometimes people do via SCCM,
# various folders do not exist, such as QuickLaunch. This doesn't matter
# as we'll use the "system" key finally and check for the "quicklaunch"
# subkey before adding any Quick Launch menu items.

# It can happen that some of the dirs[] entires refer to folders that do not
# exist, in which case, the 2nd entry of the value tuple is a sub-class of
# Exception.

dirs_src = {
    "system": {
        "desktop": get_folder_path(FOLDERID.PublicDesktop),
        "start": get_folder_path(FOLDERID.CommonPrograms),
        "documents": get_folder_path(FOLDERID.PublicDocuments),
        "profile": get_folder_path(FOLDERID.Profile),
    },
    "user": {
        "desktop": get_folder_path(FOLDERID.Desktop),
        "start": get_folder_path(FOLDERID.Programs),
        "quicklaunch": get_folder_path(FOLDERID.QuickLaunch),
        "documents": get_folder_path(FOLDERID.Documents),
        "profile": get_folder_path(FOLDERID.Profile),
        "localappdata": get_folder_path(FOLDERID.LocalAppData),
    },
}


def folder_path(preferred_mode, check_other_mode, key):
    '''This function implements all heuristics and workarounds for messed up
    KNOWNFOLDERID registry values. It's also verbose (OutputDebugStringW)
    about whether fallbacks worked or whether they would have worked if
    check_other_mode had been allowed.
    '''
    other_mode = 'system' if preferred_mode == 'user' else 'user'
    path, exception = dirs_src[preferred_mode][key]
    if not exception:
        return path
    logger.info(
        "WARNING: menuinst key: '%s'\n"
        "                 path: '%s'\n"
        "     .. excepted with: '%s' in knownfolders.py, implementing workarounds .."
        % (key, path, type(exception).__name__)
    )
    # Since I have seen 'user', 'documents' set as '\\vmware-host\Shared Folders\Documents'
    # when there's no such server, we check 'user', 'profile' + '\Documents' before maybe
    # trying the other_mode (though I have chickened out on that idea).
    if preferred_mode == 'user' and key == 'documents':
        user_profile, exception = dirs_src['user']['profile']
        if not exception:
            path = os.path.join(user_profile, 'Documents')
            if os.access(path, os.W_OK):
                logger.info("  .. worked-around to: '%s'" % (path))
                return path
    path, exception = dirs_src[other_mode][key]
    # Do not fall back to something we cannot write to.
    if exception:
        if check_other_mode:
            logger.info(
                "     .. despite 'check_other_mode'\n"
                "        and 'other_mode' 'path' of '%s'\n"
                "        it excepted with: '%s' in knownfolders.py"
                % (path, type(exception).__name__)
            )
        else:
            logger.info(
                "     .. 'check_other_mode' is False,\n"
                "        and 'other_mode' 'path' is '%s'\n"
                "        but it excepted anyway with: '%s' in knownfolders.py"
                % (path, type(exception).__name__)
            )
        return None
    if not check_other_mode:
        logger.info(
            "     .. due to lack of 'check_other_mode' not picking\n"
            "        non-excepting path of '%s'\n in knownfolders.py" % (path)
        )
        return None
    return path


def windows_terminal_settings_files(mode: str) -> List[Path]:
    """Return all possible locations of the settings.json files for the Windows Terminal.

    See the Microsoft documentation for details:
    https://learn.microsoft.com/en-us/windows/terminal/install#settings-json-file
    """
    if mode != "user":
        return []
    localappdata = folder_path(mode, False, "localappdata")
    packages = Path(localappdata) / "Packages"
    profile_locations = [
        # Stable
        *[
            Path(terminal, "LocalState", "settings.json")
            for terminal in packages.glob("Microsoft.WindowsTerminal_*")
        ],
        # Preview
        *[
            Path(terminal, "LocalState", "settings.json")
            for terminal in packages.glob("Microsoft.WindowsTerminalPreview_*")
        ],
    ]
    # Unpackaged (Scoop, Chocolatey, etc.)
    unpackaged_path = Path(localappdata, "Microsoft", "Windows Terminal", "settings.json")
    if unpackaged_path.parent.exists():
        profile_locations.append(unpackaged_path)
    return profile_locations
