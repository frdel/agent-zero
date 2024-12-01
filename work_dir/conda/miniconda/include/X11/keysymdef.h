/***********************************************************
Copyright 1987, 1994, 1998  The Open Group

Permission to use, copy, modify, distribute, and sell this software and its
documentation for any purpose is hereby granted without fee, provided that
the above copyright notice appear in all copies and that both that
copyright notice and this permission notice appear in supporting
documentation.

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE OPEN GROUP BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

Except as contained in this notice, the name of The Open Group shall
not be used in advertising or otherwise to promote the sale, use or
other dealings in this Software without prior written authorization
from The Open Group.


Copyright 1987 by Digital Equipment Corporation, Maynard, Massachusetts

                        All Rights Reserved

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted,
provided that the above copyright notice appear in all copies and that
both that copyright notice and this permission notice appear in
supporting documentation, and that the name of Digital not be
used in advertising or publicity pertaining to distribution of the
software without specific, written prior permission.

DIGITAL DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE, INCLUDING
ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO EVENT SHALL
DIGITAL BE LIABLE FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR
ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS
SOFTWARE.

******************************************************************/

/*
 * The "X11 Window System Protocol" standard defines in Appendix A the
 * keysym codes. These 29-bit integer values identify characters or
 * functions associated with each key (e.g., via the visible
 * engraving) of a keyboard layout. This file assigns mnemonic macro
 * names for these keysyms.
 *
 * This file is also compiled (by src/util/makekeys.c in libX11) into
 * hash tables that can be accessed with X11 library functions such as
 * XStringToKeysym() and XKeysymToString().
 *
 * Where a keysym corresponds one-to-one to an ISO 10646 / Unicode
 * character, this is noted in a comment that provides both the U+xxxx
 * Unicode position, as well as the official Unicode name of the
 * character.
 *
 * Where the correspondence is either not one-to-one or semantically
 * unclear, the Unicode position and name are enclosed in
 * parentheses. Such legacy keysyms should be considered deprecated
 * and are not recommended for use in future keyboard mappings.
 *
 * For any future extension of the keysyms with characters already
 * found in ISO 10646 / Unicode, the following algorithm shall be
 * used. The new keysym code position will simply be the character's
 * Unicode number plus 0x01000000. The keysym values in the range
 * 0x01000100 to 0x0110ffff are reserved to represent Unicode
 * characters in the range U+0100 to U+10FFFF.
 *
 * While most newer Unicode-based X11 clients do already accept
 * Unicode-mapped keysyms in the range 0x01000100 to 0x0110ffff, it
 * will remain necessary for clients -- in the interest of
 * compatibility with existing servers -- to also understand the
 * existing legacy keysym values in the range 0x0100 to 0x20ff.
 *
 * Where several mnemonic names are defined for the same keysym in this
 * file, all but the first one listed should be considered deprecated.
 *
 * Mnemonic names for keysyms are defined in this file with lines
 * that match one of these Perl regular expressions:
 *
 *    /^\#define XK_([a-zA-Z_0-9]+)\s+0x([0-9a-f]+)\s*\/\* U\+([0-9A-F]{4,6}) (.*) \*\/\s*$/
 *    /^\#define XK_([a-zA-Z_0-9]+)\s+0x([0-9a-f]+)\s*\/\*\(U\+([0-9A-F]{4,6}) (.*)\)\*\/\s*$/
 *    /^\#define XK_([a-zA-Z_0-9]+)\s+0x([0-9a-f]+)\s*(\/\*\s*(.*)\s*\*\/)?\s*$/
 *
 * Before adding new keysyms, please do consider the following: In
 * addition to the keysym names defined in this file, the
 * XStringToKeysym() and XKeysymToString() functions will also handle
 * any keysym string of the form "U0020" to "U007E" and "U00A0" to
 * "U10FFFF" for all possible Unicode characters. In other words,
 * every possible Unicode character has already a keysym string
 * defined algorithmically, even if it is not listed here. Therefore,
 * defining an additional keysym macro is only necessary where a
 * non-hexadecimal mnemonic name is needed, or where the new keysym
 * does not represent any existing Unicode character.
 *
 * When adding new keysyms to this file, do not forget to also update the
 * following as needed:
 *
 *   - the mappings in src/KeyBind.c in the libX11 repo
 *     https://gitlab.freedesktop.org/xorg/lib/libx11
 *
 *   - the protocol specification in specs/keysyms.xml in this repo
 *     https://gitlab.freedesktop.org/xorg/proto/xorgproto
 *
 */

#define XK_VoidSymbol                  0xffffff  /* Void symbol */

#ifdef XK_MISCELLANY
/*
 * TTY function keys, cleverly chosen to map to ASCII, for convenience of
 * programming, but could have been arbitrary (at the cost of lookup
 * tables in client code).
 */

#define XK_BackSpace                     0xff08  /* Back space, back char */
#define XK_Tab                           0xff09
#define XK_Linefeed                      0xff0a  /* Linefeed, LF */
#define XK_Clear                         0xff0b
#define XK_Return                        0xff0d  /* Return, enter */
#define XK_Pause                         0xff13  /* Pause, hold */
#define XK_Scroll_Lock                   0xff14
#define XK_Sys_Req                       0xff15
#define XK_Escape                        0xff1b
#define XK_Delete                        0xffff  /* Delete, rubout */



/* International & multi-key character composition */

#define XK_Multi_key                     0xff20  /* Multi-key character compose */
#define XK_Codeinput                     0xff37
#define XK_SingleCandidate               0xff3c
#define XK_MultipleCandidate             0xff3d
#define XK_PreviousCandidate             0xff3e

/* Japanese keyboard support */

#define XK_Kanji                         0xff21  /* Kanji, Kanji convert */
#define XK_Muhenkan                      0xff22  /* Cancel Conversion */
#define XK_Henkan_Mode                   0xff23  /* Start/Stop Conversion */
#define XK_Henkan                        0xff23  /* Alias for Henkan_Mode */
#define XK_Romaji                        0xff24  /* to Romaji */
#define XK_Hiragana                      0xff25  /* to Hiragana */
#define XK_Katakana                      0xff26  /* to Katakana */
#define XK_Hiragana_Katakana             0xff27  /* Hiragana/Katakana toggle */
#define XK_Zenkaku                       0xff28  /* to Zenkaku */
#define XK_Hankaku                       0xff29  /* to Hankaku */
#define XK_Zenkaku_Hankaku               0xff2a  /* Zenkaku/Hankaku toggle */
#define XK_Touroku                       0xff2b  /* Add to Dictionary */
#define XK_Massyo                        0xff2c  /* Delete from Dictionary */
#define XK_Kana_Lock                     0xff2d  /* Kana Lock */
#define XK_Kana_Shift                    0xff2e  /* Kana Shift */
#define XK_Eisu_Shift                    0xff2f  /* Alphanumeric Shift */
#define XK_Eisu_toggle                   0xff30  /* Alphanumeric toggle */
#define XK_Kanji_Bangou                  0xff37  /* Codeinput */
#define XK_Zen_Koho                      0xff3d  /* Multiple/All Candidate(s) */
#define XK_Mae_Koho                      0xff3e  /* Previous Candidate */

/* 0xff31 thru 0xff3f are under XK_KOREAN */

/* Cursor control & motion */

#define XK_Home                          0xff50
#define XK_Left                          0xff51  /* Move left, left arrow */
#define XK_Up                            0xff52  /* Move up, up arrow */
#define XK_Right                         0xff53  /* Move right, right arrow */
#define XK_Down                          0xff54  /* Move down, down arrow */
#define XK_Prior                         0xff55  /* Prior, previous */
#define XK_Page_Up                       0xff55
#define XK_Next                          0xff56  /* Next */
#define XK_Page_Down                     0xff56
#define XK_End                           0xff57  /* EOL */
#define XK_Begin                         0xff58  /* BOL */

/* Special Windows keyboard keys */

#define XK_Win_L		0xFF5B	/* Left-hand Windows */
#define XK_Win_R		0xFF5C	/* Right-hand Windows */
#define XK_App			0xFF5D	/* Menu key */


/* Misc functions */

#define XK_Select                        0xff60  /* Select, mark */
#define XK_Print                         0xff61
#define XK_Execute                       0xff62  /* Execute, run, do */
#define XK_Insert                        0xff63  /* Insert, insert here */
#define XK_Undo                          0xff65
#define XK_Redo                          0xff66  /* Redo, again */
#define XK_Menu                          0xff67
#define XK_Find                          0xff68  /* Find, search */
#define XK_Cancel                        0xff69  /* Cancel, stop, abort, exit */
#define XK_Help                          0xff6a  /* Help */
#define XK_Break                         0xff6b
#define XK_Mode_switch                   0xff7e  /* Character set switch */
#define XK_script_switch                 0xff7e  /* Alias for mode_switch */
#define XK_Num_Lock                      0xff7f

/* Keypad functions, keypad numbers cleverly chosen to map to ASCII */

#define XK_KP_Space                      0xff80  /* Space */
#define XK_KP_Tab                        0xff89
#define XK_KP_Enter                      0xff8d  /* Enter */
#define XK_KP_F1                         0xff91  /* PF1, KP_A, ... */
#define XK_KP_F2                         0xff92
#define XK_KP_F3                         0xff93
#define XK_KP_F4                         0xff94
#define XK_KP_Home                       0xff95
#define XK_KP_Left                       0xff96
#define XK_KP_Up                         0xff97
#define XK_KP_Right                      0xff98
#define XK_KP_Down                       0xff99
#define XK_KP_Prior                      0xff9a
#define XK_KP_Page_Up                    0xff9a
#define XK_KP_Next                       0xff9b
#define XK_KP_Page_Down                  0xff9b
#define XK_KP_End                        0xff9c
#define XK_KP_Begin                      0xff9d
#define XK_KP_Insert                     0xff9e
#define XK_KP_Delete                     0xff9f
#define XK_KP_Equal                      0xffbd  /* Equals */
#define XK_KP_Multiply                   0xffaa
#define XK_KP_Add                        0xffab
#define XK_KP_Separator                  0xffac  /* Separator, often comma */
#define XK_KP_Subtract                   0xffad
#define XK_KP_Decimal                    0xffae
#define XK_KP_Divide                     0xffaf

#define XK_KP_0                          0xffb0
#define XK_KP_1                          0xffb1
#define XK_KP_2                          0xffb2
#define XK_KP_3                          0xffb3
#define XK_KP_4                          0xffb4
#define XK_KP_5                          0xffb5
#define XK_KP_6                          0xffb6
#define XK_KP_7                          0xffb7
#define XK_KP_8                          0xffb8
#define XK_KP_9                          0xffb9



/*
 * Auxiliary functions; note the duplicate definitions for left and right
 * function keys;  Sun keyboards and a few other manufacturers have such
 * function key groups on the left and/or right sides of the keyboard.
 * We've not found a keyboard with more than 35 function keys total.
 */

#define XK_F1                            0xffbe
#define XK_F2                            0xffbf
#define XK_F3                            0xffc0
#define XK_F4                            0xffc1
#define XK_F5                            0xffc2
#define XK_F6                            0xffc3
#define XK_F7                            0xffc4
#define XK_F8                            0xffc5
#define XK_F9                            0xffc6
#define XK_F10                           0xffc7
#define XK_F11                           0xffc8
#define XK_L1                            0xffc8
#define XK_F12                           0xffc9
#define XK_L2                            0xffc9
#define XK_F13                           0xffca
#define XK_L3                            0xffca
#define XK_F14                           0xffcb
#define XK_L4                            0xffcb
#define XK_F15                           0xffcc
#define XK_L5                            0xffcc
#define XK_F16                           0xffcd
#define XK_L6                            0xffcd
#define XK_F17                           0xffce
#define XK_L7                            0xffce
#define XK_F18                           0xffcf
#define XK_L8                            0xffcf
#define XK_F19                           0xffd0
#define XK_L9                            0xffd0
#define XK_F20                           0xffd1
#define XK_L10                           0xffd1
#define XK_F21                           0xffd2
#define XK_R1                            0xffd2
#define XK_F22                           0xffd3
#define XK_R2                            0xffd3
#define XK_F23                           0xffd4
#define XK_R3                            0xffd4
#define XK_F24                           0xffd5
#define XK_R4                            0xffd5
#define XK_F25                           0xffd6
#define XK_R5                            0xffd6
#define XK_F26                           0xffd7
#define XK_R6                            0xffd7
#define XK_F27                           0xffd8
#define XK_R7                            0xffd8
#define XK_F28                           0xffd9
#define XK_R8                            0xffd9
#define XK_F29                           0xffda
#define XK_R9                            0xffda
#define XK_F30                           0xffdb
#define XK_R10                           0xffdb
#define XK_F31                           0xffdc
#define XK_R11                           0xffdc
#define XK_F32                           0xffdd
#define XK_R12                           0xffdd
#define XK_F33                           0xffde
#define XK_R13                           0xffde
#define XK_F34                           0xffdf
#define XK_R14                           0xffdf
#define XK_F35                           0xffe0
#define XK_R15                           0xffe0

/* Modifiers */

#define XK_Shift_L                       0xffe1  /* Left shift */
#define XK_Shift_R                       0xffe2  /* Right shift */
#define XK_Control_L                     0xffe3  /* Left control */
#define XK_Control_R                     0xffe4  /* Right control */
#define XK_Caps_Lock                     0xffe5  /* Caps lock */
#define XK_Shift_Lock                    0xffe6  /* Shift lock */

#define XK_Meta_L                        0xffe7  /* Left meta */
#define XK_Meta_R                        0xffe8  /* Right meta */
#define XK_Alt_L                         0xffe9  /* Left alt */
#define XK_Alt_R                         0xffea  /* Right alt */
#define XK_Super_L                       0xffeb  /* Left super */
#define XK_Super_R                       0xffec  /* Right super */
#define XK_Hyper_L                       0xffed  /* Left hyper */
#define XK_Hyper_R                       0xffee  /* Right hyper */
#endif /* XK_MISCELLANY */

/*
 * Keyboard (XKB) Extension function and modifier keys
 * (from Appendix C of "The X Keyboard Extension: Protocol Specification")
 * Byte 3 = 0xfe
 */

#ifdef XK_XKB_KEYS
#define XK_ISO_Lock                      0xfe01
#define XK_ISO_Level2_Latch              0xfe02
#define XK_ISO_Level3_Shift              0xfe03
#define XK_ISO_Level3_Latch              0xfe04
#define XK_ISO_Level3_Lock               0xfe05
#define XK_ISO_Level5_Shift              0xfe11
#define XK_ISO_Level5_Latch              0xfe12
#define XK_ISO_Level5_Lock               0xfe13
#define XK_ISO_Group_Shift               0xff7e  /* Alias for mode_switch */
#define XK_ISO_Group_Latch               0xfe06
#define XK_ISO_Group_Lock                0xfe07
#define XK_ISO_Next_Group                0xfe08
#define XK_ISO_Next_Group_Lock           0xfe09
#define XK_ISO_Prev_Group                0xfe0a
#define XK_ISO_Prev_Group_Lock           0xfe0b
#define XK_ISO_First_Group               0xfe0c
#define XK_ISO_First_Group_Lock          0xfe0d
#define XK_ISO_Last_Group                0xfe0e
#define XK_ISO_Last_Group_Lock           0xfe0f

#define XK_ISO_Left_Tab                  0xfe20
#define XK_ISO_Move_Line_Up              0xfe21
#define XK_ISO_Move_Line_Down            0xfe22
#define XK_ISO_Partial_Line_Up           0xfe23
#define XK_ISO_Partial_Line_Down         0xfe24
#define XK_ISO_Partial_Space_Left        0xfe25
#define XK_ISO_Partial_Space_Right       0xfe26
#define XK_ISO_Set_Margin_Left           0xfe27
#define XK_ISO_Set_Margin_Right          0xfe28
#define XK_ISO_Release_Margin_Left       0xfe29
#define XK_ISO_Release_Margin_Right      0xfe2a
#define XK_ISO_Release_Both_Margins      0xfe2b
#define XK_ISO_Fast_Cursor_Left          0xfe2c
#define XK_ISO_Fast_Cursor_Right         0xfe2d
#define XK_ISO_Fast_Cursor_Up            0xfe2e
#define XK_ISO_Fast_Cursor_Down          0xfe2f
#define XK_ISO_Continuous_Underline      0xfe30
#define XK_ISO_Discontinuous_Underline   0xfe31
#define XK_ISO_Emphasize                 0xfe32
#define XK_ISO_Center_Object             0xfe33
#define XK_ISO_Enter                     0xfe34

#define XK_dead_grave                    0xfe50
#define XK_dead_acute                    0xfe51
#define XK_dead_circumflex               0xfe52
#define XK_dead_tilde                    0xfe53
#define XK_dead_perispomeni              0xfe53  /* alias for dead_tilde */
#define XK_dead_macron                   0xfe54
#define XK_dead_breve                    0xfe55
#define XK_dead_abovedot                 0xfe56
#define XK_dead_diaeresis                0xfe57
#define XK_dead_abovering                0xfe58
#define XK_dead_doubleacute              0xfe59
#define XK_dead_caron                    0xfe5a
#define XK_dead_cedilla                  0xfe5b
#define XK_dead_ogonek                   0xfe5c
#define XK_dead_iota                     0xfe5d
#define XK_dead_voiced_sound             0xfe5e
#define XK_dead_semivoiced_sound         0xfe5f
#define XK_dead_belowdot                 0xfe60
#define XK_dead_hook                     0xfe61
#define XK_dead_horn                     0xfe62
#define XK_dead_stroke                   0xfe63
#define XK_dead_abovecomma               0xfe64
#define XK_dead_psili                    0xfe64  /* alias for dead_abovecomma */
#define XK_dead_abovereversedcomma       0xfe65
#define XK_dead_dasia                    0xfe65  /* alias for dead_abovereversedcomma */
#define XK_dead_doublegrave              0xfe66
#define XK_dead_belowring                0xfe67
#define XK_dead_belowmacron              0xfe68
#define XK_dead_belowcircumflex          0xfe69
#define XK_dead_belowtilde               0xfe6a
#define XK_dead_belowbreve               0xfe6b
#define XK_dead_belowdiaeresis           0xfe6c
#define XK_dead_invertedbreve            0xfe6d
#define XK_dead_belowcomma               0xfe6e
#define XK_dead_currency                 0xfe6f

/* extra dead elements for German T3 layout */
#define XK_dead_lowline                  0xfe90
#define XK_dead_aboveverticalline        0xfe91
#define XK_dead_belowverticalline        0xfe92
#define XK_dead_longsolidusoverlay       0xfe93

/* dead vowels for universal syllable entry */
#define XK_dead_a                        0xfe80
#define XK_dead_A                        0xfe81
#define XK_dead_e                        0xfe82
#define XK_dead_E                        0xfe83
#define XK_dead_i                        0xfe84
#define XK_dead_I                        0xfe85
#define XK_dead_o                        0xfe86
#define XK_dead_O                        0xfe87
#define XK_dead_u                        0xfe88
#define XK_dead_U                        0xfe89
#define XK_dead_schwa                    0xfe8a
#define XK_dead_SCHWA                    0xfe8b
#define XK_dead_small_schwa              0xfe8a  /* deprecated, remove in 2025 */
#define XK_dead_capital_schwa            0xfe8b  /* deprecated, remove in 2025 */

#define XK_dead_greek                    0xfe8c

#define XK_First_Virtual_Screen          0xfed0
#define XK_Prev_Virtual_Screen           0xfed1
#define XK_Next_Virtual_Screen           0xfed2
#define XK_Last_Virtual_Screen           0xfed4
#define XK_Terminate_Server              0xfed5

#define XK_AccessX_Enable                0xfe70
#define XK_AccessX_Feedback_Enable       0xfe71
#define XK_RepeatKeys_Enable             0xfe72
#define XK_SlowKeys_Enable               0xfe73
#define XK_BounceKeys_Enable             0xfe74
#define XK_StickyKeys_Enable             0xfe75
#define XK_MouseKeys_Enable              0xfe76
#define XK_MouseKeys_Accel_Enable        0xfe77
#define XK_Overlay1_Enable               0xfe78
#define XK_Overlay2_Enable               0xfe79
#define XK_AudibleBell_Enable            0xfe7a

#define XK_Pointer_Left                  0xfee0
#define XK_Pointer_Right                 0xfee1
#define XK_Pointer_Up                    0xfee2
#define XK_Pointer_Down                  0xfee3
#define XK_Pointer_UpLeft                0xfee4
#define XK_Pointer_UpRight               0xfee5
#define XK_Pointer_DownLeft              0xfee6
#define XK_Pointer_DownRight             0xfee7
#define XK_Pointer_Button_Dflt           0xfee8
#define XK_Pointer_Button1               0xfee9
#define XK_Pointer_Button2               0xfeea
#define XK_Pointer_Button3               0xfeeb
#define XK_Pointer_Button4               0xfeec
#define XK_Pointer_Button5               0xfeed
#define XK_Pointer_DblClick_Dflt         0xfeee
#define XK_Pointer_DblClick1             0xfeef
#define XK_Pointer_DblClick2             0xfef0
#define XK_Pointer_DblClick3             0xfef1
#define XK_Pointer_DblClick4             0xfef2
#define XK_Pointer_DblClick5             0xfef3
#define XK_Pointer_Drag_Dflt             0xfef4
#define XK_Pointer_Drag1                 0xfef5
#define XK_Pointer_Drag2                 0xfef6
#define XK_Pointer_Drag3                 0xfef7
#define XK_Pointer_Drag4                 0xfef8
#define XK_Pointer_Drag5                 0xfefd

#define XK_Pointer_EnableKeys            0xfef9
#define XK_Pointer_Accelerate            0xfefa
#define XK_Pointer_DfltBtnNext           0xfefb
#define XK_Pointer_DfltBtnPrev           0xfefc

/* Single-Stroke Multiple-Character N-Graph Keysyms For The X Input Method */

#define XK_ch                            0xfea0
#define XK_Ch                            0xfea1
#define XK_CH                            0xfea2
#define XK_c_h                           0xfea3
#define XK_C_h                           0xfea4
#define XK_C_H                           0xfea5

#endif /* XK_XKB_KEYS */

/*
 * 3270 Terminal Keys
 * Byte 3 = 0xfd
 */

#ifdef XK_3270
#define XK_3270_Duplicate                0xfd01
#define XK_3270_FieldMark                0xfd02
#define XK_3270_Right2                   0xfd03
#define XK_3270_Left2                    0xfd04
#define XK_3270_BackTab                  0xfd05
#define XK_3270_EraseEOF                 0xfd06
#define XK_3270_EraseInput               0xfd07
#define XK_3270_Reset                    0xfd08
#define XK_3270_Quit                     0xfd09
#define XK_3270_PA1                      0xfd0a
#define XK_3270_PA2                      0xfd0b
#define XK_3270_PA3                      0xfd0c
#define XK_3270_Test                     0xfd0d
#define XK_3270_Attn                     0xfd0e
#define XK_3270_CursorBlink              0xfd0f
#define XK_3270_AltCursor                0xfd10
#define XK_3270_KeyClick                 0xfd11
#define XK_3270_Jump                     0xfd12
#define XK_3270_Ident                    0xfd13
#define XK_3270_Rule                     0xfd14
#define XK_3270_Copy                     0xfd15
#define XK_3270_Play                     0xfd16
#define XK_3270_Setup                    0xfd17
#define XK_3270_Record                   0xfd18
#define XK_3270_ChangeScreen             0xfd19
#define XK_3270_DeleteWord               0xfd1a
#define XK_3270_ExSelect                 0xfd1b
#define XK_3270_CursorSelect             0xfd1c
#define XK_3270_PrintScreen              0xfd1d
#define XK_3270_Enter                    0xfd1e
#endif /* XK_3270 */

/*
 * Latin 1
 * (ISO/IEC 8859-1 = Unicode U+0020..U+00FF)
 * Byte 3 = 0
 */
#ifdef XK_LATIN1
#define XK_space                         0x0020  /* U+0020 SPACE */
#define XK_exclam                        0x0021  /* U+0021 EXCLAMATION MARK */
#define XK_quotedbl                      0x0022  /* U+0022 QUOTATION MARK */
#define XK_numbersign                    0x0023  /* U+0023 NUMBER SIGN */
#define XK_dollar                        0x0024  /* U+0024 DOLLAR SIGN */
#define XK_percent                       0x0025  /* U+0025 PERCENT SIGN */
#define XK_ampersand                     0x0026  /* U+0026 AMPERSAND */
#define XK_apostrophe                    0x0027  /* U+0027 APOSTROPHE */
#define XK_quoteright                    0x0027  /* deprecated */
#define XK_parenleft                     0x0028  /* U+0028 LEFT PARENTHESIS */
#define XK_parenright                    0x0029  /* U+0029 RIGHT PARENTHESIS */
#define XK_asterisk                      0x002a  /* U+002A ASTERISK */
#define XK_plus                          0x002b  /* U+002B PLUS SIGN */
#define XK_comma                         0x002c  /* U+002C COMMA */
#define XK_minus                         0x002d  /* U+002D HYPHEN-MINUS */
#define XK_period                        0x002e  /* U+002E FULL STOP */
#define XK_slash                         0x002f  /* U+002F SOLIDUS */
#define XK_0                             0x0030  /* U+0030 DIGIT ZERO */
#define XK_1                             0x0031  /* U+0031 DIGIT ONE */
#define XK_2                             0x0032  /* U+0032 DIGIT TWO */
#define XK_3                             0x0033  /* U+0033 DIGIT THREE */
#define XK_4                             0x0034  /* U+0034 DIGIT FOUR */
#define XK_5                             0x0035  /* U+0035 DIGIT FIVE */
#define XK_6                             0x0036  /* U+0036 DIGIT SIX */
#define XK_7                             0x0037  /* U+0037 DIGIT SEVEN */
#define XK_8                             0x0038  /* U+0038 DIGIT EIGHT */
#define XK_9                             0x0039  /* U+0039 DIGIT NINE */
#define XK_colon                         0x003a  /* U+003A COLON */
#define XK_semicolon                     0x003b  /* U+003B SEMICOLON */
#define XK_less                          0x003c  /* U+003C LESS-THAN SIGN */
#define XK_equal                         0x003d  /* U+003D EQUALS SIGN */
#define XK_greater                       0x003e  /* U+003E GREATER-THAN SIGN */
#define XK_question                      0x003f  /* U+003F QUESTION MARK */
#define XK_at                            0x0040  /* U+0040 COMMERCIAL AT */
#define XK_A                             0x0041  /* U+0041 LATIN CAPITAL LETTER A */
#define XK_B                             0x0042  /* U+0042 LATIN CAPITAL LETTER B */
#define XK_C                             0x0043  /* U+0043 LATIN CAPITAL LETTER C */
#define XK_D                             0x0044  /* U+0044 LATIN CAPITAL LETTER D */
#define XK_E                             0x0045  /* U+0045 LATIN CAPITAL LETTER E */
#define XK_F                             0x0046  /* U+0046 LATIN CAPITAL LETTER F */
#define XK_G                             0x0047  /* U+0047 LATIN CAPITAL LETTER G */
#define XK_H                             0x0048  /* U+0048 LATIN CAPITAL LETTER H */
#define XK_I                             0x0049  /* U+0049 LATIN CAPITAL LETTER I */
#define XK_J                             0x004a  /* U+004A LATIN CAPITAL LETTER J */
#define XK_K                             0x004b  /* U+004B LATIN CAPITAL LETTER K */
#define XK_L                             0x004c  /* U+004C LATIN CAPITAL LETTER L */
#define XK_M                             0x004d  /* U+004D LATIN CAPITAL LETTER M */
#define XK_N                             0x004e  /* U+004E LATIN CAPITAL LETTER N */
#define XK_O                             0x004f  /* U+004F LATIN CAPITAL LETTER O */
#define XK_P                             0x0050  /* U+0050 LATIN CAPITAL LETTER P */
#define XK_Q                             0x0051  /* U+0051 LATIN CAPITAL LETTER Q */
#define XK_R                             0x0052  /* U+0052 LATIN CAPITAL LETTER R */
#define XK_S                             0x0053  /* U+0053 LATIN CAPITAL LETTER S */
#define XK_T                             0x0054  /* U+0054 LATIN CAPITAL LETTER T */
#define XK_U                             0x0055  /* U+0055 LATIN CAPITAL LETTER U */
#define XK_V                             0x0056  /* U+0056 LATIN CAPITAL LETTER V */
#define XK_W                             0x0057  /* U+0057 LATIN CAPITAL LETTER W */
#define XK_X                             0x0058  /* U+0058 LATIN CAPITAL LETTER X */
#define XK_Y                             0x0059  /* U+0059 LATIN CAPITAL LETTER Y */
#define XK_Z                             0x005a  /* U+005A LATIN CAPITAL LETTER Z */
#define XK_bracketleft                   0x005b  /* U+005B LEFT SQUARE BRACKET */
#define XK_backslash                     0x005c  /* U+005C REVERSE SOLIDUS */
#define XK_bracketright                  0x005d  /* U+005D RIGHT SQUARE BRACKET */
#define XK_asciicircum                   0x005e  /* U+005E CIRCUMFLEX ACCENT */
#define XK_underscore                    0x005f  /* U+005F LOW LINE */
#define XK_grave                         0x0060  /* U+0060 GRAVE ACCENT */
#define XK_quoteleft                     0x0060  /* deprecated */
#define XK_a                             0x0061  /* U+0061 LATIN SMALL LETTER A */
#define XK_b                             0x0062  /* U+0062 LATIN SMALL LETTER B */
#define XK_c                             0x0063  /* U+0063 LATIN SMALL LETTER C */
#define XK_d                             0x0064  /* U+0064 LATIN SMALL LETTER D */
#define XK_e                             0x0065  /* U+0065 LATIN SMALL LETTER E */
#define XK_f                             0x0066  /* U+0066 LATIN SMALL LETTER F */
#define XK_g                             0x0067  /* U+0067 LATIN SMALL LETTER G */
#define XK_h                             0x0068  /* U+0068 LATIN SMALL LETTER H */
#define XK_i                             0x0069  /* U+0069 LATIN SMALL LETTER I */
#define XK_j                             0x006a  /* U+006A LATIN SMALL LETTER J */
#define XK_k                             0x006b  /* U+006B LATIN SMALL LETTER K */
#define XK_l                             0x006c  /* U+006C LATIN SMALL LETTER L */
#define XK_m                             0x006d  /* U+006D LATIN SMALL LETTER M */
#define XK_n                             0x006e  /* U+006E LATIN SMALL LETTER N */
#define XK_o                             0x006f  /* U+006F LATIN SMALL LETTER O */
#define XK_p                             0x0070  /* U+0070 LATIN SMALL LETTER P */
#define XK_q                             0x0071  /* U+0071 LATIN SMALL LETTER Q */
#define XK_r                             0x0072  /* U+0072 LATIN SMALL LETTER R */
#define XK_s                             0x0073  /* U+0073 LATIN SMALL LETTER S */
#define XK_t                             0x0074  /* U+0074 LATIN SMALL LETTER T */
#define XK_u                             0x0075  /* U+0075 LATIN SMALL LETTER U */
#define XK_v                             0x0076  /* U+0076 LATIN SMALL LETTER V */
#define XK_w                             0x0077  /* U+0077 LATIN SMALL LETTER W */
#define XK_x                             0x0078  /* U+0078 LATIN SMALL LETTER X */
#define XK_y                             0x0079  /* U+0079 LATIN SMALL LETTER Y */
#define XK_z                             0x007a  /* U+007A LATIN SMALL LETTER Z */
#define XK_braceleft                     0x007b  /* U+007B LEFT CURLY BRACKET */
#define XK_bar                           0x007c  /* U+007C VERTICAL LINE */
#define XK_braceright                    0x007d  /* U+007D RIGHT CURLY BRACKET */
#define XK_asciitilde                    0x007e  /* U+007E TILDE */

#define XK_nobreakspace                  0x00a0  /* U+00A0 NO-BREAK SPACE */
#define XK_exclamdown                    0x00a1  /* U+00A1 INVERTED EXCLAMATION MARK */
#define XK_cent                          0x00a2  /* U+00A2 CENT SIGN */
#define XK_sterling                      0x00a3  /* U+00A3 POUND SIGN */
#define XK_currency                      0x00a4  /* U+00A4 CURRENCY SIGN */
#define XK_yen                           0x00a5  /* U+00A5 YEN SIGN */
#define XK_brokenbar                     0x00a6  /* U+00A6 BROKEN BAR */
#define XK_section                       0x00a7  /* U+00A7 SECTION SIGN */
#define XK_diaeresis                     0x00a8  /* U+00A8 DIAERESIS */
#define XK_copyright                     0x00a9  /* U+00A9 COPYRIGHT SIGN */
#define XK_ordfeminine                   0x00aa  /* U+00AA FEMININE ORDINAL INDICATOR */
#define XK_guillemetleft                 0x00ab  /* U+00AB LEFT-POINTING DOUBLE ANGLE QUOTATION MARK */
#define XK_guillemotleft                 0x00ab  /* deprecated misspelling */
#define XK_notsign                       0x00ac  /* U+00AC NOT SIGN */
#define XK_hyphen                        0x00ad  /* U+00AD SOFT HYPHEN */
#define XK_registered                    0x00ae  /* U+00AE REGISTERED SIGN */
#define XK_macron                        0x00af  /* U+00AF MACRON */
#define XK_degree                        0x00b0  /* U+00B0 DEGREE SIGN */
#define XK_plusminus                     0x00b1  /* U+00B1 PLUS-MINUS SIGN */
#define XK_twosuperior                   0x00b2  /* U+00B2 SUPERSCRIPT TWO */
#define XK_threesuperior                 0x00b3  /* U+00B3 SUPERSCRIPT THREE */
#define XK_acute                         0x00b4  /* U+00B4 ACUTE ACCENT */
#define XK_mu                            0x00b5  /* U+00B5 MICRO SIGN */
#define XK_paragraph                     0x00b6  /* U+00B6 PILCROW SIGN */
#define XK_periodcentered                0x00b7  /* U+00B7 MIDDLE DOT */
#define XK_cedilla                       0x00b8  /* U+00B8 CEDILLA */
#define XK_onesuperior                   0x00b9  /* U+00B9 SUPERSCRIPT ONE */
#define XK_ordmasculine                  0x00ba  /* U+00BA MASCULINE ORDINAL INDICATOR */
#define XK_masculine                     0x00ba  /* deprecated inconsistent name */
#define XK_guillemetright                0x00bb  /* U+00BB RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK */
#define XK_guillemotright                0x00bb  /* deprecated misspelling */
#define XK_onequarter                    0x00bc  /* U+00BC VULGAR FRACTION ONE QUARTER */
#define XK_onehalf                       0x00bd  /* U+00BD VULGAR FRACTION ONE HALF */
#define XK_threequarters                 0x00be  /* U+00BE VULGAR FRACTION THREE QUARTERS */
#define XK_questiondown                  0x00bf  /* U+00BF INVERTED QUESTION MARK */
#define XK_Agrave                        0x00c0  /* U+00C0 LATIN CAPITAL LETTER A WITH GRAVE */
#define XK_Aacute                        0x00c1  /* U+00C1 LATIN CAPITAL LETTER A WITH ACUTE */
#define XK_Acircumflex                   0x00c2  /* U+00C2 LATIN CAPITAL LETTER A WITH CIRCUMFLEX */
#define XK_Atilde                        0x00c3  /* U+00C3 LATIN CAPITAL LETTER A WITH TILDE */
#define XK_Adiaeresis                    0x00c4  /* U+00C4 LATIN CAPITAL LETTER A WITH DIAERESIS */
#define XK_Aring                         0x00c5  /* U+00C5 LATIN CAPITAL LETTER A WITH RING ABOVE */
#define XK_AE                            0x00c6  /* U+00C6 LATIN CAPITAL LETTER AE */
#define XK_Ccedilla                      0x00c7  /* U+00C7 LATIN CAPITAL LETTER C WITH CEDILLA */
#define XK_Egrave                        0x00c8  /* U+00C8 LATIN CAPITAL LETTER E WITH GRAVE */
#define XK_Eacute                        0x00c9  /* U+00C9 LATIN CAPITAL LETTER E WITH ACUTE */
#define XK_Ecircumflex                   0x00ca  /* U+00CA LATIN CAPITAL LETTER E WITH CIRCUMFLEX */
#define XK_Ediaeresis                    0x00cb  /* U+00CB LATIN CAPITAL LETTER E WITH DIAERESIS */
#define XK_Igrave                        0x00cc  /* U+00CC LATIN CAPITAL LETTER I WITH GRAVE */
#define XK_Iacute                        0x00cd  /* U+00CD LATIN CAPITAL LETTER I WITH ACUTE */
#define XK_Icircumflex                   0x00ce  /* U+00CE LATIN CAPITAL LETTER I WITH CIRCUMFLEX */
#define XK_Idiaeresis                    0x00cf  /* U+00CF LATIN CAPITAL LETTER I WITH DIAERESIS */
#define XK_ETH                           0x00d0  /* U+00D0 LATIN CAPITAL LETTER ETH */
#define XK_Eth                           0x00d0  /* deprecated */
#define XK_Ntilde                        0x00d1  /* U+00D1 LATIN CAPITAL LETTER N WITH TILDE */
#define XK_Ograve                        0x00d2  /* U+00D2 LATIN CAPITAL LETTER O WITH GRAVE */
#define XK_Oacute                        0x00d3  /* U+00D3 LATIN CAPITAL LETTER O WITH ACUTE */
#define XK_Ocircumflex                   0x00d4  /* U+00D4 LATIN CAPITAL LETTER O WITH CIRCUMFLEX */
#define XK_Otilde                        0x00d5  /* U+00D5 LATIN CAPITAL LETTER O WITH TILDE */
#define XK_Odiaeresis                    0x00d6  /* U+00D6 LATIN CAPITAL LETTER O WITH DIAERESIS */
#define XK_multiply                      0x00d7  /* U+00D7 MULTIPLICATION SIGN */
#define XK_Oslash                        0x00d8  /* U+00D8 LATIN CAPITAL LETTER O WITH STROKE */
#define XK_Ooblique                      0x00d8  /* U+00D8 LATIN CAPITAL LETTER O WITH STROKE */
#define XK_Ugrave                        0x00d9  /* U+00D9 LATIN CAPITAL LETTER U WITH GRAVE */
#define XK_Uacute                        0x00da  /* U+00DA LATIN CAPITAL LETTER U WITH ACUTE */
#define XK_Ucircumflex                   0x00db  /* U+00DB LATIN CAPITAL LETTER U WITH CIRCUMFLEX */
#define XK_Udiaeresis                    0x00dc  /* U+00DC LATIN CAPITAL LETTER U WITH DIAERESIS */
#define XK_Yacute                        0x00dd  /* U+00DD LATIN CAPITAL LETTER Y WITH ACUTE */
#define XK_THORN                         0x00de  /* U+00DE LATIN CAPITAL LETTER THORN */
#define XK_Thorn                         0x00de  /* deprecated */
#define XK_ssharp                        0x00df  /* U+00DF LATIN SMALL LETTER SHARP S */
#define XK_agrave                        0x00e0  /* U+00E0 LATIN SMALL LETTER A WITH GRAVE */
#define XK_aacute                        0x00e1  /* U+00E1 LATIN SMALL LETTER A WITH ACUTE */
#define XK_acircumflex                   0x00e2  /* U+00E2 LATIN SMALL LETTER A WITH CIRCUMFLEX */
#define XK_atilde                        0x00e3  /* U+00E3 LATIN SMALL LETTER A WITH TILDE */
#define XK_adiaeresis                    0x00e4  /* U+00E4 LATIN SMALL LETTER A WITH DIAERESIS */
#define XK_aring                         0x00e5  /* U+00E5 LATIN SMALL LETTER A WITH RING ABOVE */
#define XK_ae                            0x00e6  /* U+00E6 LATIN SMALL LETTER AE */
#define XK_ccedilla                      0x00e7  /* U+00E7 LATIN SMALL LETTER C WITH CEDILLA */
#define XK_egrave                        0x00e8  /* U+00E8 LATIN SMALL LETTER E WITH GRAVE */
#define XK_eacute                        0x00e9  /* U+00E9 LATIN SMALL LETTER E WITH ACUTE */
#define XK_ecircumflex                   0x00ea  /* U+00EA LATIN SMALL LETTER E WITH CIRCUMFLEX */
#define XK_ediaeresis                    0x00eb  /* U+00EB LATIN SMALL LETTER E WITH DIAERESIS */
#define XK_igrave                        0x00ec  /* U+00EC LATIN SMALL LETTER I WITH GRAVE */
#define XK_iacute                        0x00ed  /* U+00ED LATIN SMALL LETTER I WITH ACUTE */
#define XK_icircumflex                   0x00ee  /* U+00EE LATIN SMALL LETTER I WITH CIRCUMFLEX */
#define XK_idiaeresis                    0x00ef  /* U+00EF LATIN SMALL LETTER I WITH DIAERESIS */
#define XK_eth                           0x00f0  /* U+00F0 LATIN SMALL LETTER ETH */
#define XK_ntilde                        0x00f1  /* U+00F1 LATIN SMALL LETTER N WITH TILDE */
#define XK_ograve                        0x00f2  /* U+00F2 LATIN SMALL LETTER O WITH GRAVE */
#define XK_oacute                        0x00f3  /* U+00F3 LATIN SMALL LETTER O WITH ACUTE */
#define XK_ocircumflex                   0x00f4  /* U+00F4 LATIN SMALL LETTER O WITH CIRCUMFLEX */
#define XK_otilde                        0x00f5  /* U+00F5 LATIN SMALL LETTER O WITH TILDE */
#define XK_odiaeresis                    0x00f6  /* U+00F6 LATIN SMALL LETTER O WITH DIAERESIS */
#define XK_division                      0x00f7  /* U+00F7 DIVISION SIGN */
#define XK_oslash                        0x00f8  /* U+00F8 LATIN SMALL LETTER O WITH STROKE */
#define XK_ooblique                      0x00f8  /* U+00F8 LATIN SMALL LETTER O WITH STROKE */
#define XK_ugrave                        0x00f9  /* U+00F9 LATIN SMALL LETTER U WITH GRAVE */
#define XK_uacute                        0x00fa  /* U+00FA LATIN SMALL LETTER U WITH ACUTE */
#define XK_ucircumflex                   0x00fb  /* U+00FB LATIN SMALL LETTER U WITH CIRCUMFLEX */
#define XK_udiaeresis                    0x00fc  /* U+00FC LATIN SMALL LETTER U WITH DIAERESIS */
#define XK_yacute                        0x00fd  /* U+00FD LATIN SMALL LETTER Y WITH ACUTE */
#define XK_thorn                         0x00fe  /* U+00FE LATIN SMALL LETTER THORN */
#define XK_ydiaeresis                    0x00ff  /* U+00FF LATIN SMALL LETTER Y WITH DIAERESIS */
#endif /* XK_LATIN1 */

/*
 * Latin 2
 * Byte 3 = 1
 */

#ifdef XK_LATIN2
#define XK_Aogonek                       0x01a1  /* U+0104 LATIN CAPITAL LETTER A WITH OGONEK */
#define XK_breve                         0x01a2  /* U+02D8 BREVE */
#define XK_Lstroke                       0x01a3  /* U+0141 LATIN CAPITAL LETTER L WITH STROKE */
#define XK_Lcaron                        0x01a5  /* U+013D LATIN CAPITAL LETTER L WITH CARON */
#define XK_Sacute                        0x01a6  /* U+015A LATIN CAPITAL LETTER S WITH ACUTE */
#define XK_Scaron                        0x01a9  /* U+0160 LATIN CAPITAL LETTER S WITH CARON */
#define XK_Scedilla                      0x01aa  /* U+015E LATIN CAPITAL LETTER S WITH CEDILLA */
#define XK_Tcaron                        0x01ab  /* U+0164 LATIN CAPITAL LETTER T WITH CARON */
#define XK_Zacute                        0x01ac  /* U+0179 LATIN CAPITAL LETTER Z WITH ACUTE */
#define XK_Zcaron                        0x01ae  /* U+017D LATIN CAPITAL LETTER Z WITH CARON */
#define XK_Zabovedot                     0x01af  /* U+017B LATIN CAPITAL LETTER Z WITH DOT ABOVE */
#define XK_aogonek                       0x01b1  /* U+0105 LATIN SMALL LETTER A WITH OGONEK */
#define XK_ogonek                        0x01b2  /* U+02DB OGONEK */
#define XK_lstroke                       0x01b3  /* U+0142 LATIN SMALL LETTER L WITH STROKE */
#define XK_lcaron                        0x01b5  /* U+013E LATIN SMALL LETTER L WITH CARON */
#define XK_sacute                        0x01b6  /* U+015B LATIN SMALL LETTER S WITH ACUTE */
#define XK_caron                         0x01b7  /* U+02C7 CARON */
#define XK_scaron                        0x01b9  /* U+0161 LATIN SMALL LETTER S WITH CARON */
#define XK_scedilla                      0x01ba  /* U+015F LATIN SMALL LETTER S WITH CEDILLA */
#define XK_tcaron                        0x01bb  /* U+0165 LATIN SMALL LETTER T WITH CARON */
#define XK_zacute                        0x01bc  /* U+017A LATIN SMALL LETTER Z WITH ACUTE */
#define XK_doubleacute                   0x01bd  /* U+02DD DOUBLE ACUTE ACCENT */
#define XK_zcaron                        0x01be  /* U+017E LATIN SMALL LETTER Z WITH CARON */
#define XK_zabovedot                     0x01bf  /* U+017C LATIN SMALL LETTER Z WITH DOT ABOVE */
#define XK_Racute                        0x01c0  /* U+0154 LATIN CAPITAL LETTER R WITH ACUTE */
#define XK_Abreve                        0x01c3  /* U+0102 LATIN CAPITAL LETTER A WITH BREVE */
#define XK_Lacute                        0x01c5  /* U+0139 LATIN CAPITAL LETTER L WITH ACUTE */
#define XK_Cacute                        0x01c6  /* U+0106 LATIN CAPITAL LETTER C WITH ACUTE */
#define XK_Ccaron                        0x01c8  /* U+010C LATIN CAPITAL LETTER C WITH CARON */
#define XK_Eogonek                       0x01ca  /* U+0118 LATIN CAPITAL LETTER E WITH OGONEK */
#define XK_Ecaron                        0x01cc  /* U+011A LATIN CAPITAL LETTER E WITH CARON */
#define XK_Dcaron                        0x01cf  /* U+010E LATIN CAPITAL LETTER D WITH CARON */
#define XK_Dstroke                       0x01d0  /* U+0110 LATIN CAPITAL LETTER D WITH STROKE */
#define XK_Nacute                        0x01d1  /* U+0143 LATIN CAPITAL LETTER N WITH ACUTE */
#define XK_Ncaron                        0x01d2  /* U+0147 LATIN CAPITAL LETTER N WITH CARON */
#define XK_Odoubleacute                  0x01d5  /* U+0150 LATIN CAPITAL LETTER O WITH DOUBLE ACUTE */
#define XK_Rcaron                        0x01d8  /* U+0158 LATIN CAPITAL LETTER R WITH CARON */
#define XK_Uring                         0x01d9  /* U+016E LATIN CAPITAL LETTER U WITH RING ABOVE */
#define XK_Udoubleacute                  0x01db  /* U+0170 LATIN CAPITAL LETTER U WITH DOUBLE ACUTE */
#define XK_Tcedilla                      0x01de  /* U+0162 LATIN CAPITAL LETTER T WITH CEDILLA */
#define XK_racute                        0x01e0  /* U+0155 LATIN SMALL LETTER R WITH ACUTE */
#define XK_abreve                        0x01e3  /* U+0103 LATIN SMALL LETTER A WITH BREVE */
#define XK_lacute                        0x01e5  /* U+013A LATIN SMALL LETTER L WITH ACUTE */
#define XK_cacute                        0x01e6  /* U+0107 LATIN SMALL LETTER C WITH ACUTE */
#define XK_ccaron                        0x01e8  /* U+010D LATIN SMALL LETTER C WITH CARON */
#define XK_eogonek                       0x01ea  /* U+0119 LATIN SMALL LETTER E WITH OGONEK */
#define XK_ecaron                        0x01ec  /* U+011B LATIN SMALL LETTER E WITH CARON */
#define XK_dcaron                        0x01ef  /* U+010F LATIN SMALL LETTER D WITH CARON */
#define XK_dstroke                       0x01f0  /* U+0111 LATIN SMALL LETTER D WITH STROKE */
#define XK_nacute                        0x01f1  /* U+0144 LATIN SMALL LETTER N WITH ACUTE */
#define XK_ncaron                        0x01f2  /* U+0148 LATIN SMALL LETTER N WITH CARON */
#define XK_odoubleacute                  0x01f5  /* U+0151 LATIN SMALL LETTER O WITH DOUBLE ACUTE */
#define XK_rcaron                        0x01f8  /* U+0159 LATIN SMALL LETTER R WITH CARON */
#define XK_uring                         0x01f9  /* U+016F LATIN SMALL LETTER U WITH RING ABOVE */
#define XK_udoubleacute                  0x01fb  /* U+0171 LATIN SMALL LETTER U WITH DOUBLE ACUTE */
#define XK_tcedilla                      0x01fe  /* U+0163 LATIN SMALL LETTER T WITH CEDILLA */
#define XK_abovedot                      0x01ff  /* U+02D9 DOT ABOVE */
#endif /* XK_LATIN2 */

/*
 * Latin 3
 * Byte 3 = 2
 */

#ifdef XK_LATIN3
#define XK_Hstroke                       0x02a1  /* U+0126 LATIN CAPITAL LETTER H WITH STROKE */
#define XK_Hcircumflex                   0x02a6  /* U+0124 LATIN CAPITAL LETTER H WITH CIRCUMFLEX */
#define XK_Iabovedot                     0x02a9  /* U+0130 LATIN CAPITAL LETTER I WITH DOT ABOVE */
#define XK_Gbreve                        0x02ab  /* U+011E LATIN CAPITAL LETTER G WITH BREVE */
#define XK_Jcircumflex                   0x02ac  /* U+0134 LATIN CAPITAL LETTER J WITH CIRCUMFLEX */
#define XK_hstroke                       0x02b1  /* U+0127 LATIN SMALL LETTER H WITH STROKE */
#define XK_hcircumflex                   0x02b6  /* U+0125 LATIN SMALL LETTER H WITH CIRCUMFLEX */
#define XK_idotless                      0x02b9  /* U+0131 LATIN SMALL LETTER DOTLESS I */
#define XK_gbreve                        0x02bb  /* U+011F LATIN SMALL LETTER G WITH BREVE */
#define XK_jcircumflex                   0x02bc  /* U+0135 LATIN SMALL LETTER J WITH CIRCUMFLEX */
#define XK_Cabovedot                     0x02c5  /* U+010A LATIN CAPITAL LETTER C WITH DOT ABOVE */
#define XK_Ccircumflex                   0x02c6  /* U+0108 LATIN CAPITAL LETTER C WITH CIRCUMFLEX */
#define XK_Gabovedot                     0x02d5  /* U+0120 LATIN CAPITAL LETTER G WITH DOT ABOVE */
#define XK_Gcircumflex                   0x02d8  /* U+011C LATIN CAPITAL LETTER G WITH CIRCUMFLEX */
#define XK_Ubreve                        0x02dd  /* U+016C LATIN CAPITAL LETTER U WITH BREVE */
#define XK_Scircumflex                   0x02de  /* U+015C LATIN CAPITAL LETTER S WITH CIRCUMFLEX */
#define XK_cabovedot                     0x02e5  /* U+010B LATIN SMALL LETTER C WITH DOT ABOVE */
#define XK_ccircumflex                   0x02e6  /* U+0109 LATIN SMALL LETTER C WITH CIRCUMFLEX */
#define XK_gabovedot                     0x02f5  /* U+0121 LATIN SMALL LETTER G WITH DOT ABOVE */
#define XK_gcircumflex                   0x02f8  /* U+011D LATIN SMALL LETTER G WITH CIRCUMFLEX */
#define XK_ubreve                        0x02fd  /* U+016D LATIN SMALL LETTER U WITH BREVE */
#define XK_scircumflex                   0x02fe  /* U+015D LATIN SMALL LETTER S WITH CIRCUMFLEX */
#endif /* XK_LATIN3 */


/*
 * Latin 4
 * Byte 3 = 3
 */

#ifdef XK_LATIN4
#define XK_kra                           0x03a2  /* U+0138 LATIN SMALL LETTER KRA */
#define XK_kappa                         0x03a2  /* deprecated */
#define XK_Rcedilla                      0x03a3  /* U+0156 LATIN CAPITAL LETTER R WITH CEDILLA */
#define XK_Itilde                        0x03a5  /* U+0128 LATIN CAPITAL LETTER I WITH TILDE */
#define XK_Lcedilla                      0x03a6  /* U+013B LATIN CAPITAL LETTER L WITH CEDILLA */
#define XK_Emacron                       0x03aa  /* U+0112 LATIN CAPITAL LETTER E WITH MACRON */
#define XK_Gcedilla                      0x03ab  /* U+0122 LATIN CAPITAL LETTER G WITH CEDILLA */
#define XK_Tslash                        0x03ac  /* U+0166 LATIN CAPITAL LETTER T WITH STROKE */
#define XK_rcedilla                      0x03b3  /* U+0157 LATIN SMALL LETTER R WITH CEDILLA */
#define XK_itilde                        0x03b5  /* U+0129 LATIN SMALL LETTER I WITH TILDE */
#define XK_lcedilla                      0x03b6  /* U+013C LATIN SMALL LETTER L WITH CEDILLA */
#define XK_emacron                       0x03ba  /* U+0113 LATIN SMALL LETTER E WITH MACRON */
#define XK_gcedilla                      0x03bb  /* U+0123 LATIN SMALL LETTER G WITH CEDILLA */
#define XK_tslash                        0x03bc  /* U+0167 LATIN SMALL LETTER T WITH STROKE */
#define XK_ENG                           0x03bd  /* U+014A LATIN CAPITAL LETTER ENG */
#define XK_eng                           0x03bf  /* U+014B LATIN SMALL LETTER ENG */
#define XK_Amacron                       0x03c0  /* U+0100 LATIN CAPITAL LETTER A WITH MACRON */
#define XK_Iogonek                       0x03c7  /* U+012E LATIN CAPITAL LETTER I WITH OGONEK */
#define XK_Eabovedot                     0x03cc  /* U+0116 LATIN CAPITAL LETTER E WITH DOT ABOVE */
#define XK_Imacron                       0x03cf  /* U+012A LATIN CAPITAL LETTER I WITH MACRON */
#define XK_Ncedilla                      0x03d1  /* U+0145 LATIN CAPITAL LETTER N WITH CEDILLA */
#define XK_Omacron                       0x03d2  /* U+014C LATIN CAPITAL LETTER O WITH MACRON */
#define XK_Kcedilla                      0x03d3  /* U+0136 LATIN CAPITAL LETTER K WITH CEDILLA */
#define XK_Uogonek                       0x03d9  /* U+0172 LATIN CAPITAL LETTER U WITH OGONEK */
#define XK_Utilde                        0x03dd  /* U+0168 LATIN CAPITAL LETTER U WITH TILDE */
#define XK_Umacron                       0x03de  /* U+016A LATIN CAPITAL LETTER U WITH MACRON */
#define XK_amacron                       0x03e0  /* U+0101 LATIN SMALL LETTER A WITH MACRON */
#define XK_iogonek                       0x03e7  /* U+012F LATIN SMALL LETTER I WITH OGONEK */
#define XK_eabovedot                     0x03ec  /* U+0117 LATIN SMALL LETTER E WITH DOT ABOVE */
#define XK_imacron                       0x03ef  /* U+012B LATIN SMALL LETTER I WITH MACRON */
#define XK_ncedilla                      0x03f1  /* U+0146 LATIN SMALL LETTER N WITH CEDILLA */
#define XK_omacron                       0x03f2  /* U+014D LATIN SMALL LETTER O WITH MACRON */
#define XK_kcedilla                      0x03f3  /* U+0137 LATIN SMALL LETTER K WITH CEDILLA */
#define XK_uogonek                       0x03f9  /* U+0173 LATIN SMALL LETTER U WITH OGONEK */
#define XK_utilde                        0x03fd  /* U+0169 LATIN SMALL LETTER U WITH TILDE */
#define XK_umacron                       0x03fe  /* U+016B LATIN SMALL LETTER U WITH MACRON */
#endif /* XK_LATIN4 */

/*
 * Latin 9
 * Byte 3 = 0x13
 */

#ifdef XK_LATIN9
#define XK_OE                            0x13bc  /* U+0152 LATIN CAPITAL LIGATURE OE */
#define XK_oe                            0x13bd  /* U+0153 LATIN SMALL LIGATURE OE */
#define XK_Ydiaeresis                    0x13be  /* U+0178 LATIN CAPITAL LETTER Y WITH DIAERESIS */
#endif /* XK_LATIN9 */

/*
 * Katakana
 * Byte 3 = 4
 */

#ifdef XK_KATAKANA
#define XK_overline                      0x047e  /* U+203E OVERLINE */
#define XK_kana_fullstop                 0x04a1  /* U+3002 IDEOGRAPHIC FULL STOP */
#define XK_kana_openingbracket           0x04a2  /* U+300C LEFT CORNER BRACKET */
#define XK_kana_closingbracket           0x04a3  /* U+300D RIGHT CORNER BRACKET */
#define XK_kana_comma                    0x04a4  /* U+3001 IDEOGRAPHIC COMMA */
#define XK_kana_conjunctive              0x04a5  /* U+30FB KATAKANA MIDDLE DOT */
#define XK_kana_middledot                0x04a5  /* deprecated */
#define XK_kana_WO                       0x04a6  /* U+30F2 KATAKANA LETTER WO */
#define XK_kana_a                        0x04a7  /* U+30A1 KATAKANA LETTER SMALL A */
#define XK_kana_i                        0x04a8  /* U+30A3 KATAKANA LETTER SMALL I */
#define XK_kana_u                        0x04a9  /* U+30A5 KATAKANA LETTER SMALL U */
#define XK_kana_e                        0x04aa  /* U+30A7 KATAKANA LETTER SMALL E */
#define XK_kana_o                        0x04ab  /* U+30A9 KATAKANA LETTER SMALL O */
#define XK_kana_ya                       0x04ac  /* U+30E3 KATAKANA LETTER SMALL YA */
#define XK_kana_yu                       0x04ad  /* U+30E5 KATAKANA LETTER SMALL YU */
#define XK_kana_yo                       0x04ae  /* U+30E7 KATAKANA LETTER SMALL YO */
#define XK_kana_tsu                      0x04af  /* U+30C3 KATAKANA LETTER SMALL TU */
#define XK_kana_tu                       0x04af  /* deprecated */
#define XK_prolongedsound                0x04b0  /* U+30FC KATAKANA-HIRAGANA PROLONGED SOUND MARK */
#define XK_kana_A                        0x04b1  /* U+30A2 KATAKANA LETTER A */
#define XK_kana_I                        0x04b2  /* U+30A4 KATAKANA LETTER I */
#define XK_kana_U                        0x04b3  /* U+30A6 KATAKANA LETTER U */
#define XK_kana_E                        0x04b4  /* U+30A8 KATAKANA LETTER E */
#define XK_kana_O                        0x04b5  /* U+30AA KATAKANA LETTER O */
#define XK_kana_KA                       0x04b6  /* U+30AB KATAKANA LETTER KA */
#define XK_kana_KI                       0x04b7  /* U+30AD KATAKANA LETTER KI */
#define XK_kana_KU                       0x04b8  /* U+30AF KATAKANA LETTER KU */
#define XK_kana_KE                       0x04b9  /* U+30B1 KATAKANA LETTER KE */
#define XK_kana_KO                       0x04ba  /* U+30B3 KATAKANA LETTER KO */
#define XK_kana_SA                       0x04bb  /* U+30B5 KATAKANA LETTER SA */
#define XK_kana_SHI                      0x04bc  /* U+30B7 KATAKANA LETTER SI */
#define XK_kana_SU                       0x04bd  /* U+30B9 KATAKANA LETTER SU */
#define XK_kana_SE                       0x04be  /* U+30BB KATAKANA LETTER SE */
#define XK_kana_SO                       0x04bf  /* U+30BD KATAKANA LETTER SO */
#define XK_kana_TA                       0x04c0  /* U+30BF KATAKANA LETTER TA */
#define XK_kana_CHI                      0x04c1  /* U+30C1 KATAKANA LETTER TI */
#define XK_kana_TI                       0x04c1  /* deprecated */
#define XK_kana_TSU                      0x04c2  /* U+30C4 KATAKANA LETTER TU */
#define XK_kana_TU                       0x04c2  /* deprecated */
#define XK_kana_TE                       0x04c3  /* U+30C6 KATAKANA LETTER TE */
#define XK_kana_TO                       0x04c4  /* U+30C8 KATAKANA LETTER TO */
#define XK_kana_NA                       0x04c5  /* U+30CA KATAKANA LETTER NA */
#define XK_kana_NI                       0x04c6  /* U+30CB KATAKANA LETTER NI */
#define XK_kana_NU                       0x04c7  /* U+30CC KATAKANA LETTER NU */
#define XK_kana_NE                       0x04c8  /* U+30CD KATAKANA LETTER NE */
#define XK_kana_NO                       0x04c9  /* U+30CE KATAKANA LETTER NO */
#define XK_kana_HA                       0x04ca  /* U+30CF KATAKANA LETTER HA */
#define XK_kana_HI                       0x04cb  /* U+30D2 KATAKANA LETTER HI */
#define XK_kana_FU                       0x04cc  /* U+30D5 KATAKANA LETTER HU */
#define XK_kana_HU                       0x04cc  /* deprecated */
#define XK_kana_HE                       0x04cd  /* U+30D8 KATAKANA LETTER HE */
#define XK_kana_HO                       0x04ce  /* U+30DB KATAKANA LETTER HO */
#define XK_kana_MA                       0x04cf  /* U+30DE KATAKANA LETTER MA */
#define XK_kana_MI                       0x04d0  /* U+30DF KATAKANA LETTER MI */
#define XK_kana_MU                       0x04d1  /* U+30E0 KATAKANA LETTER MU */
#define XK_kana_ME                       0x04d2  /* U+30E1 KATAKANA LETTER ME */
#define XK_kana_MO                       0x04d3  /* U+30E2 KATAKANA LETTER MO */
#define XK_kana_YA                       0x04d4  /* U+30E4 KATAKANA LETTER YA */
#define XK_kana_YU                       0x04d5  /* U+30E6 KATAKANA LETTER YU */
#define XK_kana_YO                       0x04d6  /* U+30E8 KATAKANA LETTER YO */
#define XK_kana_RA                       0x04d7  /* U+30E9 KATAKANA LETTER RA */
#define XK_kana_RI                       0x04d8  /* U+30EA KATAKANA LETTER RI */
#define XK_kana_RU                       0x04d9  /* U+30EB KATAKANA LETTER RU */
#define XK_kana_RE                       0x04da  /* U+30EC KATAKANA LETTER RE */
#define XK_kana_RO                       0x04db  /* U+30ED KATAKANA LETTER RO */
#define XK_kana_WA                       0x04dc  /* U+30EF KATAKANA LETTER WA */
#define XK_kana_N                        0x04dd  /* U+30F3 KATAKANA LETTER N */
#define XK_voicedsound                   0x04de  /* U+309B KATAKANA-HIRAGANA VOICED SOUND MARK */
#define XK_semivoicedsound               0x04df  /* U+309C KATAKANA-HIRAGANA SEMI-VOICED SOUND MARK */
#define XK_kana_switch                   0xff7e  /* Alias for mode_switch */
#endif /* XK_KATAKANA */

/*
 * Arabic
 * Byte 3 = 5
 */

#ifdef XK_ARABIC
#define XK_Arabic_comma                  0x05ac  /* U+060C ARABIC COMMA */
#define XK_Arabic_semicolon              0x05bb  /* U+061B ARABIC SEMICOLON */
#define XK_Arabic_question_mark          0x05bf  /* U+061F ARABIC QUESTION MARK */
#define XK_Arabic_hamza                  0x05c1  /* U+0621 ARABIC LETTER HAMZA */
#define XK_Arabic_maddaonalef            0x05c2  /* U+0622 ARABIC LETTER ALEF WITH MADDA ABOVE */
#define XK_Arabic_hamzaonalef            0x05c3  /* U+0623 ARABIC LETTER ALEF WITH HAMZA ABOVE */
#define XK_Arabic_hamzaonwaw             0x05c4  /* U+0624 ARABIC LETTER WAW WITH HAMZA ABOVE */
#define XK_Arabic_hamzaunderalef         0x05c5  /* U+0625 ARABIC LETTER ALEF WITH HAMZA BELOW */
#define XK_Arabic_hamzaonyeh             0x05c6  /* U+0626 ARABIC LETTER YEH WITH HAMZA ABOVE */
#define XK_Arabic_alef                   0x05c7  /* U+0627 ARABIC LETTER ALEF */
#define XK_Arabic_beh                    0x05c8  /* U+0628 ARABIC LETTER BEH */
#define XK_Arabic_tehmarbuta             0x05c9  /* U+0629 ARABIC LETTER TEH MARBUTA */
#define XK_Arabic_teh                    0x05ca  /* U+062A ARABIC LETTER TEH */
#define XK_Arabic_theh                   0x05cb  /* U+062B ARABIC LETTER THEH */
#define XK_Arabic_jeem                   0x05cc  /* U+062C ARABIC LETTER JEEM */
#define XK_Arabic_hah                    0x05cd  /* U+062D ARABIC LETTER HAH */
#define XK_Arabic_khah                   0x05ce  /* U+062E ARABIC LETTER KHAH */
#define XK_Arabic_dal                    0x05cf  /* U+062F ARABIC LETTER DAL */
#define XK_Arabic_thal                   0x05d0  /* U+0630 ARABIC LETTER THAL */
#define XK_Arabic_ra                     0x05d1  /* U+0631 ARABIC LETTER REH */
#define XK_Arabic_zain                   0x05d2  /* U+0632 ARABIC LETTER ZAIN */
#define XK_Arabic_seen                   0x05d3  /* U+0633 ARABIC LETTER SEEN */
#define XK_Arabic_sheen                  0x05d4  /* U+0634 ARABIC LETTER SHEEN */
#define XK_Arabic_sad                    0x05d5  /* U+0635 ARABIC LETTER SAD */
#define XK_Arabic_dad                    0x05d6  /* U+0636 ARABIC LETTER DAD */
#define XK_Arabic_tah                    0x05d7  /* U+0637 ARABIC LETTER TAH */
#define XK_Arabic_zah                    0x05d8  /* U+0638 ARABIC LETTER ZAH */
#define XK_Arabic_ain                    0x05d9  /* U+0639 ARABIC LETTER AIN */
#define XK_Arabic_ghain                  0x05da  /* U+063A ARABIC LETTER GHAIN */
#define XK_Arabic_tatweel                0x05e0  /* U+0640 ARABIC TATWEEL */
#define XK_Arabic_feh                    0x05e1  /* U+0641 ARABIC LETTER FEH */
#define XK_Arabic_qaf                    0x05e2  /* U+0642 ARABIC LETTER QAF */
#define XK_Arabic_kaf                    0x05e3  /* U+0643 ARABIC LETTER KAF */
#define XK_Arabic_lam                    0x05e4  /* U+0644 ARABIC LETTER LAM */
#define XK_Arabic_meem                   0x05e5  /* U+0645 ARABIC LETTER MEEM */
#define XK_Arabic_noon                   0x05e6  /* U+0646 ARABIC LETTER NOON */
#define XK_Arabic_ha                     0x05e7  /* U+0647 ARABIC LETTER HEH */
#define XK_Arabic_heh                    0x05e7  /* deprecated */
#define XK_Arabic_waw                    0x05e8  /* U+0648 ARABIC LETTER WAW */
#define XK_Arabic_alefmaksura            0x05e9  /* U+0649 ARABIC LETTER ALEF MAKSURA */
#define XK_Arabic_yeh                    0x05ea  /* U+064A ARABIC LETTER YEH */
#define XK_Arabic_fathatan               0x05eb  /* U+064B ARABIC FATHATAN */
#define XK_Arabic_dammatan               0x05ec  /* U+064C ARABIC DAMMATAN */
#define XK_Arabic_kasratan               0x05ed  /* U+064D ARABIC KASRATAN */
#define XK_Arabic_fatha                  0x05ee  /* U+064E ARABIC FATHA */
#define XK_Arabic_damma                  0x05ef  /* U+064F ARABIC DAMMA */
#define XK_Arabic_kasra                  0x05f0  /* U+0650 ARABIC KASRA */
#define XK_Arabic_shadda                 0x05f1  /* U+0651 ARABIC SHADDA */
#define XK_Arabic_sukun                  0x05f2  /* U+0652 ARABIC SUKUN */
#define XK_Arabic_switch                 0xff7e  /* Alias for mode_switch */
#endif /* XK_ARABIC */

/*
 * Cyrillic
 * Byte 3 = 6
 */
#ifdef XK_CYRILLIC
#define XK_Serbian_dje                   0x06a1  /* U+0452 CYRILLIC SMALL LETTER DJE */
#define XK_Macedonia_gje                 0x06a2  /* U+0453 CYRILLIC SMALL LETTER GJE */
#define XK_Cyrillic_io                   0x06a3  /* U+0451 CYRILLIC SMALL LETTER IO */
#define XK_Ukrainian_ie                  0x06a4  /* U+0454 CYRILLIC SMALL LETTER UKRAINIAN IE */
#define XK_Ukranian_je                   0x06a4  /* deprecated */
#define XK_Macedonia_dse                 0x06a5  /* U+0455 CYRILLIC SMALL LETTER DZE */
#define XK_Ukrainian_i                   0x06a6  /* U+0456 CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I */
#define XK_Ukranian_i                    0x06a6  /* deprecated */
#define XK_Ukrainian_yi                  0x06a7  /* U+0457 CYRILLIC SMALL LETTER YI */
#define XK_Ukranian_yi                   0x06a7  /* deprecated */
#define XK_Cyrillic_je                   0x06a8  /* U+0458 CYRILLIC SMALL LETTER JE */
#define XK_Serbian_je                    0x06a8  /* deprecated */
#define XK_Cyrillic_lje                  0x06a9  /* U+0459 CYRILLIC SMALL LETTER LJE */
#define XK_Serbian_lje                   0x06a9  /* deprecated */
#define XK_Cyrillic_nje                  0x06aa  /* U+045A CYRILLIC SMALL LETTER NJE */
#define XK_Serbian_nje                   0x06aa  /* deprecated */
#define XK_Serbian_tshe                  0x06ab  /* U+045B CYRILLIC SMALL LETTER TSHE */
#define XK_Macedonia_kje                 0x06ac  /* U+045C CYRILLIC SMALL LETTER KJE */
#define XK_Ukrainian_ghe_with_upturn     0x06ad  /* U+0491 CYRILLIC SMALL LETTER GHE WITH UPTURN */
#define XK_Byelorussian_shortu           0x06ae  /* U+045E CYRILLIC SMALL LETTER SHORT U */
#define XK_Cyrillic_dzhe                 0x06af  /* U+045F CYRILLIC SMALL LETTER DZHE */
#define XK_Serbian_dze                   0x06af  /* deprecated */
#define XK_numerosign                    0x06b0  /* U+2116 NUMERO SIGN */
#define XK_Serbian_DJE                   0x06b1  /* U+0402 CYRILLIC CAPITAL LETTER DJE */
#define XK_Macedonia_GJE                 0x06b2  /* U+0403 CYRILLIC CAPITAL LETTER GJE */
#define XK_Cyrillic_IO                   0x06b3  /* U+0401 CYRILLIC CAPITAL LETTER IO */
#define XK_Ukrainian_IE                  0x06b4  /* U+0404 CYRILLIC CAPITAL LETTER UKRAINIAN IE */
#define XK_Ukranian_JE                   0x06b4  /* deprecated */
#define XK_Macedonia_DSE                 0x06b5  /* U+0405 CYRILLIC CAPITAL LETTER DZE */
#define XK_Ukrainian_I                   0x06b6  /* U+0406 CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I */
#define XK_Ukranian_I                    0x06b6  /* deprecated */
#define XK_Ukrainian_YI                  0x06b7  /* U+0407 CYRILLIC CAPITAL LETTER YI */
#define XK_Ukranian_YI                   0x06b7  /* deprecated */
#define XK_Cyrillic_JE                   0x06b8  /* U+0408 CYRILLIC CAPITAL LETTER JE */
#define XK_Serbian_JE                    0x06b8  /* deprecated */
#define XK_Cyrillic_LJE                  0x06b9  /* U+0409 CYRILLIC CAPITAL LETTER LJE */
#define XK_Serbian_LJE                   0x06b9  /* deprecated */
#define XK_Cyrillic_NJE                  0x06ba  /* U+040A CYRILLIC CAPITAL LETTER NJE */
#define XK_Serbian_NJE                   0x06ba  /* deprecated */
#define XK_Serbian_TSHE                  0x06bb  /* U+040B CYRILLIC CAPITAL LETTER TSHE */
#define XK_Macedonia_KJE                 0x06bc  /* U+040C CYRILLIC CAPITAL LETTER KJE */
#define XK_Ukrainian_GHE_WITH_UPTURN     0x06bd  /* U+0490 CYRILLIC CAPITAL LETTER GHE WITH UPTURN */
#define XK_Byelorussian_SHORTU           0x06be  /* U+040E CYRILLIC CAPITAL LETTER SHORT U */
#define XK_Cyrillic_DZHE                 0x06bf  /* U+040F CYRILLIC CAPITAL LETTER DZHE */
#define XK_Serbian_DZE                   0x06bf  /* deprecated */
#define XK_Cyrillic_yu                   0x06c0  /* U+044E CYRILLIC SMALL LETTER YU */
#define XK_Cyrillic_a                    0x06c1  /* U+0430 CYRILLIC SMALL LETTER A */
#define XK_Cyrillic_be                   0x06c2  /* U+0431 CYRILLIC SMALL LETTER BE */
#define XK_Cyrillic_tse                  0x06c3  /* U+0446 CYRILLIC SMALL LETTER TSE */
#define XK_Cyrillic_de                   0x06c4  /* U+0434 CYRILLIC SMALL LETTER DE */
#define XK_Cyrillic_ie                   0x06c5  /* U+0435 CYRILLIC SMALL LETTER IE */
#define XK_Cyrillic_ef                   0x06c6  /* U+0444 CYRILLIC SMALL LETTER EF */
#define XK_Cyrillic_ghe                  0x06c7  /* U+0433 CYRILLIC SMALL LETTER GHE */
#define XK_Cyrillic_ha                   0x06c8  /* U+0445 CYRILLIC SMALL LETTER HA */
#define XK_Cyrillic_i                    0x06c9  /* U+0438 CYRILLIC SMALL LETTER I */
#define XK_Cyrillic_shorti               0x06ca  /* U+0439 CYRILLIC SMALL LETTER SHORT I */
#define XK_Cyrillic_ka                   0x06cb  /* U+043A CYRILLIC SMALL LETTER KA */
#define XK_Cyrillic_el                   0x06cc  /* U+043B CYRILLIC SMALL LETTER EL */
#define XK_Cyrillic_em                   0x06cd  /* U+043C CYRILLIC SMALL LETTER EM */
#define XK_Cyrillic_en                   0x06ce  /* U+043D CYRILLIC SMALL LETTER EN */
#define XK_Cyrillic_o                    0x06cf  /* U+043E CYRILLIC SMALL LETTER O */
#define XK_Cyrillic_pe                   0x06d0  /* U+043F CYRILLIC SMALL LETTER PE */
#define XK_Cyrillic_ya                   0x06d1  /* U+044F CYRILLIC SMALL LETTER YA */
#define XK_Cyrillic_er                   0x06d2  /* U+0440 CYRILLIC SMALL LETTER ER */
#define XK_Cyrillic_es                   0x06d3  /* U+0441 CYRILLIC SMALL LETTER ES */
#define XK_Cyrillic_te                   0x06d4  /* U+0442 CYRILLIC SMALL LETTER TE */
#define XK_Cyrillic_u                    0x06d5  /* U+0443 CYRILLIC SMALL LETTER U */
#define XK_Cyrillic_zhe                  0x06d6  /* U+0436 CYRILLIC SMALL LETTER ZHE */
#define XK_Cyrillic_ve                   0x06d7  /* U+0432 CYRILLIC SMALL LETTER VE */
#define XK_Cyrillic_softsign             0x06d8  /* U+044C CYRILLIC SMALL LETTER SOFT SIGN */
#define XK_Cyrillic_yeru                 0x06d9  /* U+044B CYRILLIC SMALL LETTER YERU */
#define XK_Cyrillic_ze                   0x06da  /* U+0437 CYRILLIC SMALL LETTER ZE */
#define XK_Cyrillic_sha                  0x06db  /* U+0448 CYRILLIC SMALL LETTER SHA */
#define XK_Cyrillic_e                    0x06dc  /* U+044D CYRILLIC SMALL LETTER E */
#define XK_Cyrillic_shcha                0x06dd  /* U+0449 CYRILLIC SMALL LETTER SHCHA */
#define XK_Cyrillic_che                  0x06de  /* U+0447 CYRILLIC SMALL LETTER CHE */
#define XK_Cyrillic_hardsign             0x06df  /* U+044A CYRILLIC SMALL LETTER HARD SIGN */
#define XK_Cyrillic_YU                   0x06e0  /* U+042E CYRILLIC CAPITAL LETTER YU */
#define XK_Cyrillic_A                    0x06e1  /* U+0410 CYRILLIC CAPITAL LETTER A */
#define XK_Cyrillic_BE                   0x06e2  /* U+0411 CYRILLIC CAPITAL LETTER BE */
#define XK_Cyrillic_TSE                  0x06e3  /* U+0426 CYRILLIC CAPITAL LETTER TSE */
#define XK_Cyrillic_DE                   0x06e4  /* U+0414 CYRILLIC CAPITAL LETTER DE */
#define XK_Cyrillic_IE                   0x06e5  /* U+0415 CYRILLIC CAPITAL LETTER IE */
#define XK_Cyrillic_EF                   0x06e6  /* U+0424 CYRILLIC CAPITAL LETTER EF */
#define XK_Cyrillic_GHE                  0x06e7  /* U+0413 CYRILLIC CAPITAL LETTER GHE */
#define XK_Cyrillic_HA                   0x06e8  /* U+0425 CYRILLIC CAPITAL LETTER HA */
#define XK_Cyrillic_I                    0x06e9  /* U+0418 CYRILLIC CAPITAL LETTER I */
#define XK_Cyrillic_SHORTI               0x06ea  /* U+0419 CYRILLIC CAPITAL LETTER SHORT I */
#define XK_Cyrillic_KA                   0x06eb  /* U+041A CYRILLIC CAPITAL LETTER KA */
#define XK_Cyrillic_EL                   0x06ec  /* U+041B CYRILLIC CAPITAL LETTER EL */
#define XK_Cyrillic_EM                   0x06ed  /* U+041C CYRILLIC CAPITAL LETTER EM */
#define XK_Cyrillic_EN                   0x06ee  /* U+041D CYRILLIC CAPITAL LETTER EN */
#define XK_Cyrillic_O                    0x06ef  /* U+041E CYRILLIC CAPITAL LETTER O */
#define XK_Cyrillic_PE                   0x06f0  /* U+041F CYRILLIC CAPITAL LETTER PE */
#define XK_Cyrillic_YA                   0x06f1  /* U+042F CYRILLIC CAPITAL LETTER YA */
#define XK_Cyrillic_ER                   0x06f2  /* U+0420 CYRILLIC CAPITAL LETTER ER */
#define XK_Cyrillic_ES                   0x06f3  /* U+0421 CYRILLIC CAPITAL LETTER ES */
#define XK_Cyrillic_TE                   0x06f4  /* U+0422 CYRILLIC CAPITAL LETTER TE */
#define XK_Cyrillic_U                    0x06f5  /* U+0423 CYRILLIC CAPITAL LETTER U */
#define XK_Cyrillic_ZHE                  0x06f6  /* U+0416 CYRILLIC CAPITAL LETTER ZHE */
#define XK_Cyrillic_VE                   0x06f7  /* U+0412 CYRILLIC CAPITAL LETTER VE */
#define XK_Cyrillic_SOFTSIGN             0x06f8  /* U+042C CYRILLIC CAPITAL LETTER SOFT SIGN */
#define XK_Cyrillic_YERU                 0x06f9  /* U+042B CYRILLIC CAPITAL LETTER YERU */
#define XK_Cyrillic_ZE                   0x06fa  /* U+0417 CYRILLIC CAPITAL LETTER ZE */
#define XK_Cyrillic_SHA                  0x06fb  /* U+0428 CYRILLIC CAPITAL LETTER SHA */
#define XK_Cyrillic_E                    0x06fc  /* U+042D CYRILLIC CAPITAL LETTER E */
#define XK_Cyrillic_SHCHA                0x06fd  /* U+0429 CYRILLIC CAPITAL LETTER SHCHA */
#define XK_Cyrillic_CHE                  0x06fe  /* U+0427 CYRILLIC CAPITAL LETTER CHE */
#define XK_Cyrillic_HARDSIGN             0x06ff  /* U+042A CYRILLIC CAPITAL LETTER HARD SIGN */
#endif /* XK_CYRILLIC */

/*
 * Greek
 * (based on an early draft of, and not quite identical to, ISO/IEC 8859-7)
 * Byte 3 = 7
 */

#ifdef XK_GREEK
#define XK_Greek_ALPHAaccent             0x07a1  /* U+0386 GREEK CAPITAL LETTER ALPHA WITH TONOS */
#define XK_Greek_EPSILONaccent           0x07a2  /* U+0388 GREEK CAPITAL LETTER EPSILON WITH TONOS */
#define XK_Greek_ETAaccent               0x07a3  /* U+0389 GREEK CAPITAL LETTER ETA WITH TONOS */
#define XK_Greek_IOTAaccent              0x07a4  /* U+038A GREEK CAPITAL LETTER IOTA WITH TONOS */
#define XK_Greek_IOTAdieresis            0x07a5  /* U+03AA GREEK CAPITAL LETTER IOTA WITH DIALYTIKA */
#define XK_Greek_IOTAdiaeresis           0x07a5  /* old typo */
#define XK_Greek_OMICRONaccent           0x07a7  /* U+038C GREEK CAPITAL LETTER OMICRON WITH TONOS */
#define XK_Greek_UPSILONaccent           0x07a8  /* U+038E GREEK CAPITAL LETTER UPSILON WITH TONOS */
#define XK_Greek_UPSILONdieresis         0x07a9  /* U+03AB GREEK CAPITAL LETTER UPSILON WITH DIALYTIKA */
#define XK_Greek_OMEGAaccent             0x07ab  /* U+038F GREEK CAPITAL LETTER OMEGA WITH TONOS */
#define XK_Greek_accentdieresis          0x07ae  /* U+0385 GREEK DIALYTIKA TONOS */
#define XK_Greek_horizbar                0x07af  /* U+2015 HORIZONTAL BAR */
#define XK_Greek_alphaaccent             0x07b1  /* U+03AC GREEK SMALL LETTER ALPHA WITH TONOS */
#define XK_Greek_epsilonaccent           0x07b2  /* U+03AD GREEK SMALL LETTER EPSILON WITH TONOS */
#define XK_Greek_etaaccent               0x07b3  /* U+03AE GREEK SMALL LETTER ETA WITH TONOS */
#define XK_Greek_iotaaccent              0x07b4  /* U+03AF GREEK SMALL LETTER IOTA WITH TONOS */
#define XK_Greek_iotadieresis            0x07b5  /* U+03CA GREEK SMALL LETTER IOTA WITH DIALYTIKA */
#define XK_Greek_iotaaccentdieresis      0x07b6  /* U+0390 GREEK SMALL LETTER IOTA WITH DIALYTIKA AND TONOS */
#define XK_Greek_omicronaccent           0x07b7  /* U+03CC GREEK SMALL LETTER OMICRON WITH TONOS */
#define XK_Greek_upsilonaccent           0x07b8  /* U+03CD GREEK SMALL LETTER UPSILON WITH TONOS */
#define XK_Greek_upsilondieresis         0x07b9  /* U+03CB GREEK SMALL LETTER UPSILON WITH DIALYTIKA */
#define XK_Greek_upsilonaccentdieresis   0x07ba  /* U+03B0 GREEK SMALL LETTER UPSILON WITH DIALYTIKA AND TONOS */
#define XK_Greek_omegaaccent             0x07bb  /* U+03CE GREEK SMALL LETTER OMEGA WITH TONOS */
#define XK_Greek_ALPHA                   0x07c1  /* U+0391 GREEK CAPITAL LETTER ALPHA */
#define XK_Greek_BETA                    0x07c2  /* U+0392 GREEK CAPITAL LETTER BETA */
#define XK_Greek_GAMMA                   0x07c3  /* U+0393 GREEK CAPITAL LETTER GAMMA */
#define XK_Greek_DELTA                   0x07c4  /* U+0394 GREEK CAPITAL LETTER DELTA */
#define XK_Greek_EPSILON                 0x07c5  /* U+0395 GREEK CAPITAL LETTER EPSILON */
#define XK_Greek_ZETA                    0x07c6  /* U+0396 GREEK CAPITAL LETTER ZETA */
#define XK_Greek_ETA                     0x07c7  /* U+0397 GREEK CAPITAL LETTER ETA */
#define XK_Greek_THETA                   0x07c8  /* U+0398 GREEK CAPITAL LETTER THETA */
#define XK_Greek_IOTA                    0x07c9  /* U+0399 GREEK CAPITAL LETTER IOTA */
#define XK_Greek_KAPPA                   0x07ca  /* U+039A GREEK CAPITAL LETTER KAPPA */
#define XK_Greek_LAMDA                   0x07cb  /* U+039B GREEK CAPITAL LETTER LAMDA */
#define XK_Greek_LAMBDA                  0x07cb  /* U+039B GREEK CAPITAL LETTER LAMDA */
#define XK_Greek_MU                      0x07cc  /* U+039C GREEK CAPITAL LETTER MU */
#define XK_Greek_NU                      0x07cd  /* U+039D GREEK CAPITAL LETTER NU */
#define XK_Greek_XI                      0x07ce  /* U+039E GREEK CAPITAL LETTER XI */
#define XK_Greek_OMICRON                 0x07cf  /* U+039F GREEK CAPITAL LETTER OMICRON */
#define XK_Greek_PI                      0x07d0  /* U+03A0 GREEK CAPITAL LETTER PI */
#define XK_Greek_RHO                     0x07d1  /* U+03A1 GREEK CAPITAL LETTER RHO */
#define XK_Greek_SIGMA                   0x07d2  /* U+03A3 GREEK CAPITAL LETTER SIGMA */
#define XK_Greek_TAU                     0x07d4  /* U+03A4 GREEK CAPITAL LETTER TAU */
#define XK_Greek_UPSILON                 0x07d5  /* U+03A5 GREEK CAPITAL LETTER UPSILON */
#define XK_Greek_PHI                     0x07d6  /* U+03A6 GREEK CAPITAL LETTER PHI */
#define XK_Greek_CHI                     0x07d7  /* U+03A7 GREEK CAPITAL LETTER CHI */
#define XK_Greek_PSI                     0x07d8  /* U+03A8 GREEK CAPITAL LETTER PSI */
#define XK_Greek_OMEGA                   0x07d9  /* U+03A9 GREEK CAPITAL LETTER OMEGA */
#define XK_Greek_alpha                   0x07e1  /* U+03B1 GREEK SMALL LETTER ALPHA */
#define XK_Greek_beta                    0x07e2  /* U+03B2 GREEK SMALL LETTER BETA */
#define XK_Greek_gamma                   0x07e3  /* U+03B3 GREEK SMALL LETTER GAMMA */
#define XK_Greek_delta                   0x07e4  /* U+03B4 GREEK SMALL LETTER DELTA */
#define XK_Greek_epsilon                 0x07e5  /* U+03B5 GREEK SMALL LETTER EPSILON */
#define XK_Greek_zeta                    0x07e6  /* U+03B6 GREEK SMALL LETTER ZETA */
#define XK_Greek_eta                     0x07e7  /* U+03B7 GREEK SMALL LETTER ETA */
#define XK_Greek_theta                   0x07e8  /* U+03B8 GREEK SMALL LETTER THETA */
#define XK_Greek_iota                    0x07e9  /* U+03B9 GREEK SMALL LETTER IOTA */
#define XK_Greek_kappa                   0x07ea  /* U+03BA GREEK SMALL LETTER KAPPA */
#define XK_Greek_lamda                   0x07eb  /* U+03BB GREEK SMALL LETTER LAMDA */
#define XK_Greek_lambda                  0x07eb  /* U+03BB GREEK SMALL LETTER LAMDA */
#define XK_Greek_mu                      0x07ec  /* U+03BC GREEK SMALL LETTER MU */
#define XK_Greek_nu                      0x07ed  /* U+03BD GREEK SMALL LETTER NU */
#define XK_Greek_xi                      0x07ee  /* U+03BE GREEK SMALL LETTER XI */
#define XK_Greek_omicron                 0x07ef  /* U+03BF GREEK SMALL LETTER OMICRON */
#define XK_Greek_pi                      0x07f0  /* U+03C0 GREEK SMALL LETTER PI */
#define XK_Greek_rho                     0x07f1  /* U+03C1 GREEK SMALL LETTER RHO */
#define XK_Greek_sigma                   0x07f2  /* U+03C3 GREEK SMALL LETTER SIGMA */
#define XK_Greek_finalsmallsigma         0x07f3  /* U+03C2 GREEK SMALL LETTER FINAL SIGMA */
#define XK_Greek_tau                     0x07f4  /* U+03C4 GREEK SMALL LETTER TAU */
#define XK_Greek_upsilon                 0x07f5  /* U+03C5 GREEK SMALL LETTER UPSILON */
#define XK_Greek_phi                     0x07f6  /* U+03C6 GREEK SMALL LETTER PHI */
#define XK_Greek_chi                     0x07f7  /* U+03C7 GREEK SMALL LETTER CHI */
#define XK_Greek_psi                     0x07f8  /* U+03C8 GREEK SMALL LETTER PSI */
#define XK_Greek_omega                   0x07f9  /* U+03C9 GREEK SMALL LETTER OMEGA */
#define XK_Greek_switch                  0xff7e  /* Alias for mode_switch */
#endif /* XK_GREEK */

/*
 * Technical
 * (from the DEC VT330/VT420 Technical Character Set, http://vt100.net/charsets/technical.html)
 * Byte 3 = 8
 */

#ifdef XK_TECHNICAL
#define XK_leftradical                   0x08a1  /* U+23B7 RADICAL SYMBOL BOTTOM */
#define XK_topleftradical                0x08a2  /*(U+250C BOX DRAWINGS LIGHT DOWN AND RIGHT)*/
#define XK_horizconnector                0x08a3  /*(U+2500 BOX DRAWINGS LIGHT HORIZONTAL)*/
#define XK_topintegral                   0x08a4  /* U+2320 TOP HALF INTEGRAL */
#define XK_botintegral                   0x08a5  /* U+2321 BOTTOM HALF INTEGRAL */
#define XK_vertconnector                 0x08a6  /*(U+2502 BOX DRAWINGS LIGHT VERTICAL)*/
#define XK_topleftsqbracket              0x08a7  /* U+23A1 LEFT SQUARE BRACKET UPPER CORNER */
#define XK_botleftsqbracket              0x08a8  /* U+23A3 LEFT SQUARE BRACKET LOWER CORNER */
#define XK_toprightsqbracket             0x08a9  /* U+23A4 RIGHT SQUARE BRACKET UPPER CORNER */
#define XK_botrightsqbracket             0x08aa  /* U+23A6 RIGHT SQUARE BRACKET LOWER CORNER */
#define XK_topleftparens                 0x08ab  /* U+239B LEFT PARENTHESIS UPPER HOOK */
#define XK_botleftparens                 0x08ac  /* U+239D LEFT PARENTHESIS LOWER HOOK */
#define XK_toprightparens                0x08ad  /* U+239E RIGHT PARENTHESIS UPPER HOOK */
#define XK_botrightparens                0x08ae  /* U+23A0 RIGHT PARENTHESIS LOWER HOOK */
#define XK_leftmiddlecurlybrace          0x08af  /* U+23A8 LEFT CURLY BRACKET MIDDLE PIECE */
#define XK_rightmiddlecurlybrace         0x08b0  /* U+23AC RIGHT CURLY BRACKET MIDDLE PIECE */
#define XK_topleftsummation              0x08b1
#define XK_botleftsummation              0x08b2
#define XK_topvertsummationconnector     0x08b3
#define XK_botvertsummationconnector     0x08b4
#define XK_toprightsummation             0x08b5
#define XK_botrightsummation             0x08b6
#define XK_rightmiddlesummation          0x08b7
#define XK_lessthanequal                 0x08bc  /* U+2264 LESS-THAN OR EQUAL TO */
#define XK_notequal                      0x08bd  /* U+2260 NOT EQUAL TO */
#define XK_greaterthanequal              0x08be  /* U+2265 GREATER-THAN OR EQUAL TO */
#define XK_integral                      0x08bf  /* U+222B INTEGRAL */
#define XK_therefore                     0x08c0  /* U+2234 THEREFORE */
#define XK_variation                     0x08c1  /* U+221D PROPORTIONAL TO */
#define XK_infinity                      0x08c2  /* U+221E INFINITY */
#define XK_nabla                         0x08c5  /* U+2207 NABLA */
#define XK_approximate                   0x08c8  /* U+223C TILDE OPERATOR */
#define XK_similarequal                  0x08c9  /* U+2243 ASYMPTOTICALLY EQUAL TO */
#define XK_ifonlyif                      0x08cd  /* U+21D4 LEFT RIGHT DOUBLE ARROW */
#define XK_implies                       0x08ce  /* U+21D2 RIGHTWARDS DOUBLE ARROW */
#define XK_identical                     0x08cf  /* U+2261 IDENTICAL TO */
#define XK_radical                       0x08d6  /* U+221A SQUARE ROOT */
#define XK_includedin                    0x08da  /* U+2282 SUBSET OF */
#define XK_includes                      0x08db  /* U+2283 SUPERSET OF */
#define XK_intersection                  0x08dc  /* U+2229 INTERSECTION */
#define XK_union                         0x08dd  /* U+222A UNION */
#define XK_logicaland                    0x08de  /* U+2227 LOGICAL AND */
#define XK_logicalor                     0x08df  /* U+2228 LOGICAL OR */
#define XK_partialderivative             0x08ef  /* U+2202 PARTIAL DIFFERENTIAL */
#define XK_function                      0x08f6  /* U+0192 LATIN SMALL LETTER F WITH HOOK */
#define XK_leftarrow                     0x08fb  /* U+2190 LEFTWARDS ARROW */
#define XK_uparrow                       0x08fc  /* U+2191 UPWARDS ARROW */
#define XK_rightarrow                    0x08fd  /* U+2192 RIGHTWARDS ARROW */
#define XK_downarrow                     0x08fe  /* U+2193 DOWNWARDS ARROW */
#endif /* XK_TECHNICAL */

/*
 * Special
 * (from the DEC VT100 Special Graphics Character Set)
 * Byte 3 = 9
 */

#ifdef XK_SPECIAL
#define XK_blank                         0x09df
#define XK_soliddiamond                  0x09e0  /* U+25C6 BLACK DIAMOND */
#define XK_checkerboard                  0x09e1  /* U+2592 MEDIUM SHADE */
#define XK_ht                            0x09e2  /* U+2409 SYMBOL FOR HORIZONTAL TABULATION */
#define XK_ff                            0x09e3  /* U+240C SYMBOL FOR FORM FEED */
#define XK_cr                            0x09e4  /* U+240D SYMBOL FOR CARRIAGE RETURN */
#define XK_lf                            0x09e5  /* U+240A SYMBOL FOR LINE FEED */
#define XK_nl                            0x09e8  /* U+2424 SYMBOL FOR NEWLINE */
#define XK_vt                            0x09e9  /* U+240B SYMBOL FOR VERTICAL TABULATION */
#define XK_lowrightcorner                0x09ea  /* U+2518 BOX DRAWINGS LIGHT UP AND LEFT */
#define XK_uprightcorner                 0x09eb  /* U+2510 BOX DRAWINGS LIGHT DOWN AND LEFT */
#define XK_upleftcorner                  0x09ec  /* U+250C BOX DRAWINGS LIGHT DOWN AND RIGHT */
#define XK_lowleftcorner                 0x09ed  /* U+2514 BOX DRAWINGS LIGHT UP AND RIGHT */
#define XK_crossinglines                 0x09ee  /* U+253C BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL */
#define XK_horizlinescan1                0x09ef  /* U+23BA HORIZONTAL SCAN LINE-1 */
#define XK_horizlinescan3                0x09f0  /* U+23BB HORIZONTAL SCAN LINE-3 */
#define XK_horizlinescan5                0x09f1  /* U+2500 BOX DRAWINGS LIGHT HORIZONTAL */
#define XK_horizlinescan7                0x09f2  /* U+23BC HORIZONTAL SCAN LINE-7 */
#define XK_horizlinescan9                0x09f3  /* U+23BD HORIZONTAL SCAN LINE-9 */
#define XK_leftt                         0x09f4  /* U+251C BOX DRAWINGS LIGHT VERTICAL AND RIGHT */
#define XK_rightt                        0x09f5  /* U+2524 BOX DRAWINGS LIGHT VERTICAL AND LEFT */
#define XK_bott                          0x09f6  /* U+2534 BOX DRAWINGS LIGHT UP AND HORIZONTAL */
#define XK_topt                          0x09f7  /* U+252C BOX DRAWINGS LIGHT DOWN AND HORIZONTAL */
#define XK_vertbar                       0x09f8  /* U+2502 BOX DRAWINGS LIGHT VERTICAL */
#endif /* XK_SPECIAL */

/*
 * Publishing
 * (these are probably from a long forgotten DEC Publishing
 * font that once shipped with DECwrite)
 * Byte 3 = 0x0a
 */

#ifdef XK_PUBLISHING
#define XK_emspace                       0x0aa1  /* U+2003 EM SPACE */
#define XK_enspace                       0x0aa2  /* U+2002 EN SPACE */
#define XK_em3space                      0x0aa3  /* U+2004 THREE-PER-EM SPACE */
#define XK_em4space                      0x0aa4  /* U+2005 FOUR-PER-EM SPACE */
#define XK_digitspace                    0x0aa5  /* U+2007 FIGURE SPACE */
#define XK_punctspace                    0x0aa6  /* U+2008 PUNCTUATION SPACE */
#define XK_thinspace                     0x0aa7  /* U+2009 THIN SPACE */
#define XK_hairspace                     0x0aa8  /* U+200A HAIR SPACE */
#define XK_emdash                        0x0aa9  /* U+2014 EM DASH */
#define XK_endash                        0x0aaa  /* U+2013 EN DASH */
#define XK_signifblank                   0x0aac  /*(U+2423 OPEN BOX)*/
#define XK_ellipsis                      0x0aae  /* U+2026 HORIZONTAL ELLIPSIS */
#define XK_doubbaselinedot               0x0aaf  /* U+2025 TWO DOT LEADER */
#define XK_onethird                      0x0ab0  /* U+2153 VULGAR FRACTION ONE THIRD */
#define XK_twothirds                     0x0ab1  /* U+2154 VULGAR FRACTION TWO THIRDS */
#define XK_onefifth                      0x0ab2  /* U+2155 VULGAR FRACTION ONE FIFTH */
#define XK_twofifths                     0x0ab3  /* U+2156 VULGAR FRACTION TWO FIFTHS */
#define XK_threefifths                   0x0ab4  /* U+2157 VULGAR FRACTION THREE FIFTHS */
#define XK_fourfifths                    0x0ab5  /* U+2158 VULGAR FRACTION FOUR FIFTHS */
#define XK_onesixth                      0x0ab6  /* U+2159 VULGAR FRACTION ONE SIXTH */
#define XK_fivesixths                    0x0ab7  /* U+215A VULGAR FRACTION FIVE SIXTHS */
#define XK_careof                        0x0ab8  /* U+2105 CARE OF */
#define XK_figdash                       0x0abb  /* U+2012 FIGURE DASH */
#define XK_leftanglebracket              0x0abc  /*(U+2329 LEFT-POINTING ANGLE BRACKET)*/
#define XK_decimalpoint                  0x0abd  /*(U+002E FULL STOP)*/
#define XK_rightanglebracket             0x0abe  /*(U+232A RIGHT-POINTING ANGLE BRACKET)*/
#define XK_marker                        0x0abf
#define XK_oneeighth                     0x0ac3  /* U+215B VULGAR FRACTION ONE EIGHTH */
#define XK_threeeighths                  0x0ac4  /* U+215C VULGAR FRACTION THREE EIGHTHS */
#define XK_fiveeighths                   0x0ac5  /* U+215D VULGAR FRACTION FIVE EIGHTHS */
#define XK_seveneighths                  0x0ac6  /* U+215E VULGAR FRACTION SEVEN EIGHTHS */
#define XK_trademark                     0x0ac9  /* U+2122 TRADE MARK SIGN */
#define XK_signaturemark                 0x0aca  /*(U+2613 SALTIRE)*/
#define XK_trademarkincircle             0x0acb
#define XK_leftopentriangle              0x0acc  /*(U+25C1 WHITE LEFT-POINTING TRIANGLE)*/
#define XK_rightopentriangle             0x0acd  /*(U+25B7 WHITE RIGHT-POINTING TRIANGLE)*/
#define XK_emopencircle                  0x0ace  /*(U+25CB WHITE CIRCLE)*/
#define XK_emopenrectangle               0x0acf  /*(U+25AF WHITE VERTICAL RECTANGLE)*/
#define XK_leftsinglequotemark           0x0ad0  /* U+2018 LEFT SINGLE QUOTATION MARK */
#define XK_rightsinglequotemark          0x0ad1  /* U+2019 RIGHT SINGLE QUOTATION MARK */
#define XK_leftdoublequotemark           0x0ad2  /* U+201C LEFT DOUBLE QUOTATION MARK */
#define XK_rightdoublequotemark          0x0ad3  /* U+201D RIGHT DOUBLE QUOTATION MARK */
#define XK_prescription                  0x0ad4  /* U+211E PRESCRIPTION TAKE */
#define XK_permille                      0x0ad5  /* U+2030 PER MILLE SIGN */
#define XK_minutes                       0x0ad6  /* U+2032 PRIME */
#define XK_seconds                       0x0ad7  /* U+2033 DOUBLE PRIME */
#define XK_latincross                    0x0ad9  /* U+271D LATIN CROSS */
#define XK_hexagram                      0x0ada
#define XK_filledrectbullet              0x0adb  /*(U+25AC BLACK RECTANGLE)*/
#define XK_filledlefttribullet           0x0adc  /*(U+25C0 BLACK LEFT-POINTING TRIANGLE)*/
#define XK_filledrighttribullet          0x0add  /*(U+25B6 BLACK RIGHT-POINTING TRIANGLE)*/
#define XK_emfilledcircle                0x0ade  /*(U+25CF BLACK CIRCLE)*/
#define XK_emfilledrect                  0x0adf  /*(U+25AE BLACK VERTICAL RECTANGLE)*/
#define XK_enopencircbullet              0x0ae0  /*(U+25E6 WHITE BULLET)*/
#define XK_enopensquarebullet            0x0ae1  /*(U+25AB WHITE SMALL SQUARE)*/
#define XK_openrectbullet                0x0ae2  /*(U+25AD WHITE RECTANGLE)*/
#define XK_opentribulletup               0x0ae3  /*(U+25B3 WHITE UP-POINTING TRIANGLE)*/
#define XK_opentribulletdown             0x0ae4  /*(U+25BD WHITE DOWN-POINTING TRIANGLE)*/
#define XK_openstar                      0x0ae5  /*(U+2606 WHITE STAR)*/
#define XK_enfilledcircbullet            0x0ae6  /*(U+2022 BULLET)*/
#define XK_enfilledsqbullet              0x0ae7  /*(U+25AA BLACK SMALL SQUARE)*/
#define XK_filledtribulletup             0x0ae8  /*(U+25B2 BLACK UP-POINTING TRIANGLE)*/
#define XK_filledtribulletdown           0x0ae9  /*(U+25BC BLACK DOWN-POINTING TRIANGLE)*/
#define XK_leftpointer                   0x0aea  /*(U+261C WHITE LEFT POINTING INDEX)*/
#define XK_rightpointer                  0x0aeb  /*(U+261E WHITE RIGHT POINTING INDEX)*/
#define XK_club                          0x0aec  /* U+2663 BLACK CLUB SUIT */
#define XK_diamond                       0x0aed  /* U+2666 BLACK DIAMOND SUIT */
#define XK_heart                         0x0aee  /* U+2665 BLACK HEART SUIT */
#define XK_maltesecross                  0x0af0  /* U+2720 MALTESE CROSS */
#define XK_dagger                        0x0af1  /* U+2020 DAGGER */
#define XK_doubledagger                  0x0af2  /* U+2021 DOUBLE DAGGER */
#define XK_checkmark                     0x0af3  /* U+2713 CHECK MARK */
#define XK_ballotcross                   0x0af4  /* U+2717 BALLOT X */
#define XK_musicalsharp                  0x0af5  /* U+266F MUSIC SHARP SIGN */
#define XK_musicalflat                   0x0af6  /* U+266D MUSIC FLAT SIGN */
#define XK_malesymbol                    0x0af7  /* U+2642 MALE SIGN */
#define XK_femalesymbol                  0x0af8  /* U+2640 FEMALE SIGN */
#define XK_telephone                     0x0af9  /* U+260E BLACK TELEPHONE */
#define XK_telephonerecorder             0x0afa  /* U+2315 TELEPHONE RECORDER */
#define XK_phonographcopyright           0x0afb  /* U+2117 SOUND RECORDING COPYRIGHT */
#define XK_caret                         0x0afc  /* U+2038 CARET */
#define XK_singlelowquotemark            0x0afd  /* U+201A SINGLE LOW-9 QUOTATION MARK */
#define XK_doublelowquotemark            0x0afe  /* U+201E DOUBLE LOW-9 QUOTATION MARK */
#define XK_cursor                        0x0aff
#endif /* XK_PUBLISHING */

/*
 * APL
 * Byte 3 = 0x0b
 */

#ifdef XK_APL
#define XK_leftcaret                     0x0ba3  /*(U+003C LESS-THAN SIGN)*/
#define XK_rightcaret                    0x0ba6  /*(U+003E GREATER-THAN SIGN)*/
#define XK_downcaret                     0x0ba8  /*(U+2228 LOGICAL OR)*/
#define XK_upcaret                       0x0ba9  /*(U+2227 LOGICAL AND)*/
#define XK_overbar                       0x0bc0  /*(U+00AF MACRON)*/
#define XK_downtack                      0x0bc2  /* U+22A4 DOWN TACK */
#define XK_upshoe                        0x0bc3  /*(U+2229 INTERSECTION)*/
#define XK_downstile                     0x0bc4  /* U+230A LEFT FLOOR */
#define XK_underbar                      0x0bc6  /*(U+005F LOW LINE)*/
#define XK_jot                           0x0bca  /* U+2218 RING OPERATOR */
#define XK_quad                          0x0bcc  /* U+2395 APL FUNCTIONAL SYMBOL QUAD */
#define XK_uptack                        0x0bce  /* U+22A5 UP TACK */
#define XK_circle                        0x0bcf  /* U+25CB WHITE CIRCLE */
#define XK_upstile                       0x0bd3  /* U+2308 LEFT CEILING */
#define XK_downshoe                      0x0bd6  /*(U+222A UNION)*/
#define XK_rightshoe                     0x0bd8  /*(U+2283 SUPERSET OF)*/
#define XK_leftshoe                      0x0bda  /*(U+2282 SUBSET OF)*/
#define XK_lefttack                      0x0bdc  /* U+22A3 LEFT TACK */
#define XK_righttack                     0x0bfc  /* U+22A2 RIGHT TACK */
#endif /* XK_APL */

/*
 * Hebrew
 * Byte 3 = 0x0c
 */

#ifdef XK_HEBREW
#define XK_hebrew_doublelowline          0x0cdf  /* U+2017 DOUBLE LOW LINE */
#define XK_hebrew_aleph                  0x0ce0  /* U+05D0 HEBREW LETTER ALEF */
#define XK_hebrew_bet                    0x0ce1  /* U+05D1 HEBREW LETTER BET */
#define XK_hebrew_beth                   0x0ce1  /* deprecated */
#define XK_hebrew_gimel                  0x0ce2  /* U+05D2 HEBREW LETTER GIMEL */
#define XK_hebrew_gimmel                 0x0ce2  /* deprecated */
#define XK_hebrew_dalet                  0x0ce3  /* U+05D3 HEBREW LETTER DALET */
#define XK_hebrew_daleth                 0x0ce3  /* deprecated */
#define XK_hebrew_he                     0x0ce4  /* U+05D4 HEBREW LETTER HE */
#define XK_hebrew_waw                    0x0ce5  /* U+05D5 HEBREW LETTER VAV */
#define XK_hebrew_zain                   0x0ce6  /* U+05D6 HEBREW LETTER ZAYIN */
#define XK_hebrew_zayin                  0x0ce6  /* deprecated */
#define XK_hebrew_chet                   0x0ce7  /* U+05D7 HEBREW LETTER HET */
#define XK_hebrew_het                    0x0ce7  /* deprecated */
#define XK_hebrew_tet                    0x0ce8  /* U+05D8 HEBREW LETTER TET */
#define XK_hebrew_teth                   0x0ce8  /* deprecated */
#define XK_hebrew_yod                    0x0ce9  /* U+05D9 HEBREW LETTER YOD */
#define XK_hebrew_finalkaph              0x0cea  /* U+05DA HEBREW LETTER FINAL KAF */
#define XK_hebrew_kaph                   0x0ceb  /* U+05DB HEBREW LETTER KAF */
#define XK_hebrew_lamed                  0x0cec  /* U+05DC HEBREW LETTER LAMED */
#define XK_hebrew_finalmem               0x0ced  /* U+05DD HEBREW LETTER FINAL MEM */
#define XK_hebrew_mem                    0x0cee  /* U+05DE HEBREW LETTER MEM */
#define XK_hebrew_finalnun               0x0cef  /* U+05DF HEBREW LETTER FINAL NUN */
#define XK_hebrew_nun                    0x0cf0  /* U+05E0 HEBREW LETTER NUN */
#define XK_hebrew_samech                 0x0cf1  /* U+05E1 HEBREW LETTER SAMEKH */
#define XK_hebrew_samekh                 0x0cf1  /* deprecated */
#define XK_hebrew_ayin                   0x0cf2  /* U+05E2 HEBREW LETTER AYIN */
#define XK_hebrew_finalpe                0x0cf3  /* U+05E3 HEBREW LETTER FINAL PE */
#define XK_hebrew_pe                     0x0cf4  /* U+05E4 HEBREW LETTER PE */
#define XK_hebrew_finalzade              0x0cf5  /* U+05E5 HEBREW LETTER FINAL TSADI */
#define XK_hebrew_finalzadi              0x0cf5  /* deprecated */
#define XK_hebrew_zade                   0x0cf6  /* U+05E6 HEBREW LETTER TSADI */
#define XK_hebrew_zadi                   0x0cf6  /* deprecated */
#define XK_hebrew_qoph                   0x0cf7  /* U+05E7 HEBREW LETTER QOF */
#define XK_hebrew_kuf                    0x0cf7  /* deprecated */
#define XK_hebrew_resh                   0x0cf8  /* U+05E8 HEBREW LETTER RESH */
#define XK_hebrew_shin                   0x0cf9  /* U+05E9 HEBREW LETTER SHIN */
#define XK_hebrew_taw                    0x0cfa  /* U+05EA HEBREW LETTER TAV */
#define XK_hebrew_taf                    0x0cfa  /* deprecated */
#define XK_Hebrew_switch                 0xff7e  /* Alias for mode_switch */
#endif /* XK_HEBREW */

/*
 * Thai
 * Byte 3 = 0x0d
 */

#ifdef XK_THAI
#define XK_Thai_kokai                    0x0da1  /* U+0E01 THAI CHARACTER KO KAI */
#define XK_Thai_khokhai                  0x0da2  /* U+0E02 THAI CHARACTER KHO KHAI */
#define XK_Thai_khokhuat                 0x0da3  /* U+0E03 THAI CHARACTER KHO KHUAT */
#define XK_Thai_khokhwai                 0x0da4  /* U+0E04 THAI CHARACTER KHO KHWAI */
#define XK_Thai_khokhon                  0x0da5  /* U+0E05 THAI CHARACTER KHO KHON */
#define XK_Thai_khorakhang               0x0da6  /* U+0E06 THAI CHARACTER KHO RAKHANG */
#define XK_Thai_ngongu                   0x0da7  /* U+0E07 THAI CHARACTER NGO NGU */
#define XK_Thai_chochan                  0x0da8  /* U+0E08 THAI CHARACTER CHO CHAN */
#define XK_Thai_choching                 0x0da9  /* U+0E09 THAI CHARACTER CHO CHING */
#define XK_Thai_chochang                 0x0daa  /* U+0E0A THAI CHARACTER CHO CHANG */
#define XK_Thai_soso                     0x0dab  /* U+0E0B THAI CHARACTER SO SO */
#define XK_Thai_chochoe                  0x0dac  /* U+0E0C THAI CHARACTER CHO CHOE */
#define XK_Thai_yoying                   0x0dad  /* U+0E0D THAI CHARACTER YO YING */
#define XK_Thai_dochada                  0x0dae  /* U+0E0E THAI CHARACTER DO CHADA */
#define XK_Thai_topatak                  0x0daf  /* U+0E0F THAI CHARACTER TO PATAK */
#define XK_Thai_thothan                  0x0db0  /* U+0E10 THAI CHARACTER THO THAN */
#define XK_Thai_thonangmontho            0x0db1  /* U+0E11 THAI CHARACTER THO NANGMONTHO */
#define XK_Thai_thophuthao               0x0db2  /* U+0E12 THAI CHARACTER THO PHUTHAO */
#define XK_Thai_nonen                    0x0db3  /* U+0E13 THAI CHARACTER NO NEN */
#define XK_Thai_dodek                    0x0db4  /* U+0E14 THAI CHARACTER DO DEK */
#define XK_Thai_totao                    0x0db5  /* U+0E15 THAI CHARACTER TO TAO */
#define XK_Thai_thothung                 0x0db6  /* U+0E16 THAI CHARACTER THO THUNG */
#define XK_Thai_thothahan                0x0db7  /* U+0E17 THAI CHARACTER THO THAHAN */
#define XK_Thai_thothong                 0x0db8  /* U+0E18 THAI CHARACTER THO THONG */
#define XK_Thai_nonu                     0x0db9  /* U+0E19 THAI CHARACTER NO NU */
#define XK_Thai_bobaimai                 0x0dba  /* U+0E1A THAI CHARACTER BO BAIMAI */
#define XK_Thai_popla                    0x0dbb  /* U+0E1B THAI CHARACTER PO PLA */
#define XK_Thai_phophung                 0x0dbc  /* U+0E1C THAI CHARACTER PHO PHUNG */
#define XK_Thai_fofa                     0x0dbd  /* U+0E1D THAI CHARACTER FO FA */
#define XK_Thai_phophan                  0x0dbe  /* U+0E1E THAI CHARACTER PHO PHAN */
#define XK_Thai_fofan                    0x0dbf  /* U+0E1F THAI CHARACTER FO FAN */
#define XK_Thai_phosamphao               0x0dc0  /* U+0E20 THAI CHARACTER PHO SAMPHAO */
#define XK_Thai_moma                     0x0dc1  /* U+0E21 THAI CHARACTER MO MA */
#define XK_Thai_yoyak                    0x0dc2  /* U+0E22 THAI CHARACTER YO YAK */
#define XK_Thai_rorua                    0x0dc3  /* U+0E23 THAI CHARACTER RO RUA */
#define XK_Thai_ru                       0x0dc4  /* U+0E24 THAI CHARACTER RU */
#define XK_Thai_loling                   0x0dc5  /* U+0E25 THAI CHARACTER LO LING */
#define XK_Thai_lu                       0x0dc6  /* U+0E26 THAI CHARACTER LU */
#define XK_Thai_wowaen                   0x0dc7  /* U+0E27 THAI CHARACTER WO WAEN */
#define XK_Thai_sosala                   0x0dc8  /* U+0E28 THAI CHARACTER SO SALA */
#define XK_Thai_sorusi                   0x0dc9  /* U+0E29 THAI CHARACTER SO RUSI */
#define XK_Thai_sosua                    0x0dca  /* U+0E2A THAI CHARACTER SO SUA */
#define XK_Thai_hohip                    0x0dcb  /* U+0E2B THAI CHARACTER HO HIP */
#define XK_Thai_lochula                  0x0dcc  /* U+0E2C THAI CHARACTER LO CHULA */
#define XK_Thai_oang                     0x0dcd  /* U+0E2D THAI CHARACTER O ANG */
#define XK_Thai_honokhuk                 0x0dce  /* U+0E2E THAI CHARACTER HO NOKHUK */
#define XK_Thai_paiyannoi                0x0dcf  /* U+0E2F THAI CHARACTER PAIYANNOI */
#define XK_Thai_saraa                    0x0dd0  /* U+0E30 THAI CHARACTER SARA A */
#define XK_Thai_maihanakat               0x0dd1  /* U+0E31 THAI CHARACTER MAI HAN-AKAT */
#define XK_Thai_saraaa                   0x0dd2  /* U+0E32 THAI CHARACTER SARA AA */
#define XK_Thai_saraam                   0x0dd3  /* U+0E33 THAI CHARACTER SARA AM */
#define XK_Thai_sarai                    0x0dd4  /* U+0E34 THAI CHARACTER SARA I */
#define XK_Thai_saraii                   0x0dd5  /* U+0E35 THAI CHARACTER SARA II */
#define XK_Thai_saraue                   0x0dd6  /* U+0E36 THAI CHARACTER SARA UE */
#define XK_Thai_sarauee                  0x0dd7  /* U+0E37 THAI CHARACTER SARA UEE */
#define XK_Thai_sarau                    0x0dd8  /* U+0E38 THAI CHARACTER SARA U */
#define XK_Thai_sarauu                   0x0dd9  /* U+0E39 THAI CHARACTER SARA UU */
#define XK_Thai_phinthu                  0x0dda  /* U+0E3A THAI CHARACTER PHINTHU */
#define XK_Thai_maihanakat_maitho        0x0dde
#define XK_Thai_baht                     0x0ddf  /* U+0E3F THAI CURRENCY SYMBOL BAHT */
#define XK_Thai_sarae                    0x0de0  /* U+0E40 THAI CHARACTER SARA E */
#define XK_Thai_saraae                   0x0de1  /* U+0E41 THAI CHARACTER SARA AE */
#define XK_Thai_sarao                    0x0de2  /* U+0E42 THAI CHARACTER SARA O */
#define XK_Thai_saraaimaimuan            0x0de3  /* U+0E43 THAI CHARACTER SARA AI MAIMUAN */
#define XK_Thai_saraaimaimalai           0x0de4  /* U+0E44 THAI CHARACTER SARA AI MAIMALAI */
#define XK_Thai_lakkhangyao              0x0de5  /* U+0E45 THAI CHARACTER LAKKHANGYAO */
#define XK_Thai_maiyamok                 0x0de6  /* U+0E46 THAI CHARACTER MAIYAMOK */
#define XK_Thai_maitaikhu                0x0de7  /* U+0E47 THAI CHARACTER MAITAIKHU */
#define XK_Thai_maiek                    0x0de8  /* U+0E48 THAI CHARACTER MAI EK */
#define XK_Thai_maitho                   0x0de9  /* U+0E49 THAI CHARACTER MAI THO */
#define XK_Thai_maitri                   0x0dea  /* U+0E4A THAI CHARACTER MAI TRI */
#define XK_Thai_maichattawa              0x0deb  /* U+0E4B THAI CHARACTER MAI CHATTAWA */
#define XK_Thai_thanthakhat              0x0dec  /* U+0E4C THAI CHARACTER THANTHAKHAT */
#define XK_Thai_nikhahit                 0x0ded  /* U+0E4D THAI CHARACTER NIKHAHIT */
#define XK_Thai_leksun                   0x0df0  /* U+0E50 THAI DIGIT ZERO */
#define XK_Thai_leknung                  0x0df1  /* U+0E51 THAI DIGIT ONE */
#define XK_Thai_leksong                  0x0df2  /* U+0E52 THAI DIGIT TWO */
#define XK_Thai_leksam                   0x0df3  /* U+0E53 THAI DIGIT THREE */
#define XK_Thai_leksi                    0x0df4  /* U+0E54 THAI DIGIT FOUR */
#define XK_Thai_lekha                    0x0df5  /* U+0E55 THAI DIGIT FIVE */
#define XK_Thai_lekhok                   0x0df6  /* U+0E56 THAI DIGIT SIX */
#define XK_Thai_lekchet                  0x0df7  /* U+0E57 THAI DIGIT SEVEN */
#define XK_Thai_lekpaet                  0x0df8  /* U+0E58 THAI DIGIT EIGHT */
#define XK_Thai_lekkao                   0x0df9  /* U+0E59 THAI DIGIT NINE */
#endif /* XK_THAI */

/*
 * Korean
 * Byte 3 = 0x0e
 */

#ifdef XK_KOREAN

#define XK_Hangul                        0xff31  /* Hangul start/stop(toggle) */
#define XK_Hangul_Start                  0xff32  /* Hangul start */
#define XK_Hangul_End                    0xff33  /* Hangul end, English start */
#define XK_Hangul_Hanja                  0xff34  /* Start Hangul->Hanja Conversion */
#define XK_Hangul_Jamo                   0xff35  /* Hangul Jamo mode */
#define XK_Hangul_Romaja                 0xff36  /* Hangul Romaja mode */
#define XK_Hangul_Codeinput              0xff37  /* Hangul code input mode */
#define XK_Hangul_Jeonja                 0xff38  /* Jeonja mode */
#define XK_Hangul_Banja                  0xff39  /* Banja mode */
#define XK_Hangul_PreHanja               0xff3a  /* Pre Hanja conversion */
#define XK_Hangul_PostHanja              0xff3b  /* Post Hanja conversion */
#define XK_Hangul_SingleCandidate        0xff3c  /* Single candidate */
#define XK_Hangul_MultipleCandidate      0xff3d  /* Multiple candidate */
#define XK_Hangul_PreviousCandidate      0xff3e  /* Previous candidate */
#define XK_Hangul_Special                0xff3f  /* Special symbols */
#define XK_Hangul_switch                 0xff7e  /* Alias for mode_switch */

/* Hangul Consonant Characters */
#define XK_Hangul_Kiyeog                 0x0ea1  /* U+3131 HANGUL LETTER KIYEOK */
#define XK_Hangul_SsangKiyeog            0x0ea2  /* U+3132 HANGUL LETTER SSANGKIYEOK */
#define XK_Hangul_KiyeogSios             0x0ea3  /* U+3133 HANGUL LETTER KIYEOK-SIOS */
#define XK_Hangul_Nieun                  0x0ea4  /* U+3134 HANGUL LETTER NIEUN */
#define XK_Hangul_NieunJieuj             0x0ea5  /* U+3135 HANGUL LETTER NIEUN-CIEUC */
#define XK_Hangul_NieunHieuh             0x0ea6  /* U+3136 HANGUL LETTER NIEUN-HIEUH */
#define XK_Hangul_Dikeud                 0x0ea7  /* U+3137 HANGUL LETTER TIKEUT */
#define XK_Hangul_SsangDikeud            0x0ea8  /* U+3138 HANGUL LETTER SSANGTIKEUT */
#define XK_Hangul_Rieul                  0x0ea9  /* U+3139 HANGUL LETTER RIEUL */
#define XK_Hangul_RieulKiyeog            0x0eaa  /* U+313A HANGUL LETTER RIEUL-KIYEOK */
#define XK_Hangul_RieulMieum             0x0eab  /* U+313B HANGUL LETTER RIEUL-MIEUM */
#define XK_Hangul_RieulPieub             0x0eac  /* U+313C HANGUL LETTER RIEUL-PIEUP */
#define XK_Hangul_RieulSios              0x0ead  /* U+313D HANGUL LETTER RIEUL-SIOS */
#define XK_Hangul_RieulTieut             0x0eae  /* U+313E HANGUL LETTER RIEUL-THIEUTH */
#define XK_Hangul_RieulPhieuf            0x0eaf  /* U+313F HANGUL LETTER RIEUL-PHIEUPH */
#define XK_Hangul_RieulHieuh             0x0eb0  /* U+3140 HANGUL LETTER RIEUL-HIEUH */
#define XK_Hangul_Mieum                  0x0eb1  /* U+3141 HANGUL LETTER MIEUM */
#define XK_Hangul_Pieub                  0x0eb2  /* U+3142 HANGUL LETTER PIEUP */
#define XK_Hangul_SsangPieub             0x0eb3  /* U+3143 HANGUL LETTER SSANGPIEUP */
#define XK_Hangul_PieubSios              0x0eb4  /* U+3144 HANGUL LETTER PIEUP-SIOS */
#define XK_Hangul_Sios                   0x0eb5  /* U+3145 HANGUL LETTER SIOS */
#define XK_Hangul_SsangSios              0x0eb6  /* U+3146 HANGUL LETTER SSANGSIOS */
#define XK_Hangul_Ieung                  0x0eb7  /* U+3147 HANGUL LETTER IEUNG */
#define XK_Hangul_Jieuj                  0x0eb8  /* U+3148 HANGUL LETTER CIEUC */
#define XK_Hangul_SsangJieuj             0x0eb9  /* U+3149 HANGUL LETTER SSANGCIEUC */
#define XK_Hangul_Cieuc                  0x0eba  /* U+314A HANGUL LETTER CHIEUCH */
#define XK_Hangul_Khieuq                 0x0ebb  /* U+314B HANGUL LETTER KHIEUKH */
#define XK_Hangul_Tieut                  0x0ebc  /* U+314C HANGUL LETTER THIEUTH */
#define XK_Hangul_Phieuf                 0x0ebd  /* U+314D HANGUL LETTER PHIEUPH */
#define XK_Hangul_Hieuh                  0x0ebe  /* U+314E HANGUL LETTER HIEUH */

/* Hangul Vowel Characters */
#define XK_Hangul_A                      0x0ebf  /* U+314F HANGUL LETTER A */
#define XK_Hangul_AE                     0x0ec0  /* U+3150 HANGUL LETTER AE */
#define XK_Hangul_YA                     0x0ec1  /* U+3151 HANGUL LETTER YA */
#define XK_Hangul_YAE                    0x0ec2  /* U+3152 HANGUL LETTER YAE */
#define XK_Hangul_EO                     0x0ec3  /* U+3153 HANGUL LETTER EO */
#define XK_Hangul_E                      0x0ec4  /* U+3154 HANGUL LETTER E */
#define XK_Hangul_YEO                    0x0ec5  /* U+3155 HANGUL LETTER YEO */
#define XK_Hangul_YE                     0x0ec6  /* U+3156 HANGUL LETTER YE */
#define XK_Hangul_O                      0x0ec7  /* U+3157 HANGUL LETTER O */
#define XK_Hangul_WA                     0x0ec8  /* U+3158 HANGUL LETTER WA */
#define XK_Hangul_WAE                    0x0ec9  /* U+3159 HANGUL LETTER WAE */
#define XK_Hangul_OE                     0x0eca  /* U+315A HANGUL LETTER OE */
#define XK_Hangul_YO                     0x0ecb  /* U+315B HANGUL LETTER YO */
#define XK_Hangul_U                      0x0ecc  /* U+315C HANGUL LETTER U */
#define XK_Hangul_WEO                    0x0ecd  /* U+315D HANGUL LETTER WEO */
#define XK_Hangul_WE                     0x0ece  /* U+315E HANGUL LETTER WE */
#define XK_Hangul_WI                     0x0ecf  /* U+315F HANGUL LETTER WI */
#define XK_Hangul_YU                     0x0ed0  /* U+3160 HANGUL LETTER YU */
#define XK_Hangul_EU                     0x0ed1  /* U+3161 HANGUL LETTER EU */
#define XK_Hangul_YI                     0x0ed2  /* U+3162 HANGUL LETTER YI */
#define XK_Hangul_I                      0x0ed3  /* U+3163 HANGUL LETTER I */

/* Hangul syllable-final (JongSeong) Characters */
#define XK_Hangul_J_Kiyeog               0x0ed4  /* U+11A8 HANGUL JONGSEONG KIYEOK */
#define XK_Hangul_J_SsangKiyeog          0x0ed5  /* U+11A9 HANGUL JONGSEONG SSANGKIYEOK */
#define XK_Hangul_J_KiyeogSios           0x0ed6  /* U+11AA HANGUL JONGSEONG KIYEOK-SIOS */
#define XK_Hangul_J_Nieun                0x0ed7  /* U+11AB HANGUL JONGSEONG NIEUN */
#define XK_Hangul_J_NieunJieuj           0x0ed8  /* U+11AC HANGUL JONGSEONG NIEUN-CIEUC */
#define XK_Hangul_J_NieunHieuh           0x0ed9  /* U+11AD HANGUL JONGSEONG NIEUN-HIEUH */
#define XK_Hangul_J_Dikeud               0x0eda  /* U+11AE HANGUL JONGSEONG TIKEUT */
#define XK_Hangul_J_Rieul                0x0edb  /* U+11AF HANGUL JONGSEONG RIEUL */
#define XK_Hangul_J_RieulKiyeog          0x0edc  /* U+11B0 HANGUL JONGSEONG RIEUL-KIYEOK */
#define XK_Hangul_J_RieulMieum           0x0edd  /* U+11B1 HANGUL JONGSEONG RIEUL-MIEUM */
#define XK_Hangul_J_RieulPieub           0x0ede  /* U+11B2 HANGUL JONGSEONG RIEUL-PIEUP */
#define XK_Hangul_J_RieulSios            0x0edf  /* U+11B3 HANGUL JONGSEONG RIEUL-SIOS */
#define XK_Hangul_J_RieulTieut           0x0ee0  /* U+11B4 HANGUL JONGSEONG RIEUL-THIEUTH */
#define XK_Hangul_J_RieulPhieuf          0x0ee1  /* U+11B5 HANGUL JONGSEONG RIEUL-PHIEUPH */
#define XK_Hangul_J_RieulHieuh           0x0ee2  /* U+11B6 HANGUL JONGSEONG RIEUL-HIEUH */
#define XK_Hangul_J_Mieum                0x0ee3  /* U+11B7 HANGUL JONGSEONG MIEUM */
#define XK_Hangul_J_Pieub                0x0ee4  /* U+11B8 HANGUL JONGSEONG PIEUP */
#define XK_Hangul_J_PieubSios            0x0ee5  /* U+11B9 HANGUL JONGSEONG PIEUP-SIOS */
#define XK_Hangul_J_Sios                 0x0ee6  /* U+11BA HANGUL JONGSEONG SIOS */
#define XK_Hangul_J_SsangSios            0x0ee7  /* U+11BB HANGUL JONGSEONG SSANGSIOS */
#define XK_Hangul_J_Ieung                0x0ee8  /* U+11BC HANGUL JONGSEONG IEUNG */
#define XK_Hangul_J_Jieuj                0x0ee9  /* U+11BD HANGUL JONGSEONG CIEUC */
#define XK_Hangul_J_Cieuc                0x0eea  /* U+11BE HANGUL JONGSEONG CHIEUCH */
#define XK_Hangul_J_Khieuq               0x0eeb  /* U+11BF HANGUL JONGSEONG KHIEUKH */
#define XK_Hangul_J_Tieut                0x0eec  /* U+11C0 HANGUL JONGSEONG THIEUTH */
#define XK_Hangul_J_Phieuf               0x0eed  /* U+11C1 HANGUL JONGSEONG PHIEUPH */
#define XK_Hangul_J_Hieuh                0x0eee  /* U+11C2 HANGUL JONGSEONG HIEUH */

/* Ancient Hangul Consonant Characters */
#define XK_Hangul_RieulYeorinHieuh       0x0eef  /* U+316D HANGUL LETTER RIEUL-YEORINHIEUH */
#define XK_Hangul_SunkyeongeumMieum      0x0ef0  /* U+3171 HANGUL LETTER KAPYEOUNMIEUM */
#define XK_Hangul_SunkyeongeumPieub      0x0ef1  /* U+3178 HANGUL LETTER KAPYEOUNPIEUP */
#define XK_Hangul_PanSios                0x0ef2  /* U+317F HANGUL LETTER PANSIOS */
#define XK_Hangul_KkogjiDalrinIeung      0x0ef3  /* U+3181 HANGUL LETTER YESIEUNG */
#define XK_Hangul_SunkyeongeumPhieuf     0x0ef4  /* U+3184 HANGUL LETTER KAPYEOUNPHIEUPH */
#define XK_Hangul_YeorinHieuh            0x0ef5  /* U+3186 HANGUL LETTER YEORINHIEUH */

/* Ancient Hangul Vowel Characters */
#define XK_Hangul_AraeA                  0x0ef6  /* U+318D HANGUL LETTER ARAEA */
#define XK_Hangul_AraeAE                 0x0ef7  /* U+318E HANGUL LETTER ARAEAE */

/* Ancient Hangul syllable-final (JongSeong) Characters */
#define XK_Hangul_J_PanSios              0x0ef8  /* U+11EB HANGUL JONGSEONG PANSIOS */
#define XK_Hangul_J_KkogjiDalrinIeung    0x0ef9  /* U+11F0 HANGUL JONGSEONG YESIEUNG */
#define XK_Hangul_J_YeorinHieuh          0x0efa  /* U+11F9 HANGUL JONGSEONG YEORINHIEUH */

/* Korean currency symbol */
#define XK_Korean_Won                    0x0eff  /*(U+20A9 WON SIGN)*/

#endif /* XK_KOREAN */

#ifdef XK_CURRENCY
#define XK_EuroSign                      0x20ac  /* U+20AC EURO SIGN */
#endif /* XK_CURRENCY */

#ifdef XK_BRAILLE
#define XK_braille_dot_1                 0xfff1
#define XK_braille_dot_2                 0xfff2
#define XK_braille_dot_3                 0xfff3
#define XK_braille_dot_4                 0xfff4
#define XK_braille_dot_5                 0xfff5
#define XK_braille_dot_6                 0xfff6
#define XK_braille_dot_7                 0xfff7
#define XK_braille_dot_8                 0xfff8
#define XK_braille_dot_9                 0xfff9
#define XK_braille_dot_10                0xfffa
#endif /* XK_BRAILLE */

/* Multimedia keys, defined same as on Linux
 * /usr/include/pkg/libxkbcommon/xkbcommon/xkbcommon-keysyms.h
 */

#define XK_XF86AudioLowerVolume	0x1008FF11   /* Volume control down        */
#define XK_XF86AudioMute	0x1008FF12   /* Mute sound from the system */
#define XK_XF86AudioRaiseVolume	0x1008FF13   /* Volume control up          */
#define XK_XF86AudioPlay	0x1008FF14   /* Start playing of audio >   */
#define XK_XF86AudioStop	0x1008FF15   /* Stop playing audio         */
#define XK_XF86AudioPrev	0x1008FF16   /* Previous track             */
#define XK_XF86AudioNext	0x1008FF17   /* Next track                 */

