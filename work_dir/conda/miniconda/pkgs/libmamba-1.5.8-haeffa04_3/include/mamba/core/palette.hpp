// Copyright (c) 2022, QuantStack and Mamba Contributors
//
// Distributed under the terms of the BSD 3-Clause License.
//
// The full license is in the file LICENSE, distributed with this software.

#ifndef MAMBA_CORE_PALETTE_HPP
#define MAMBA_CORE_PALETTE_HPP

#include <fmt/color.h>

namespace mamba
{

    struct Palette
    {
        /** Something that is possible or exsists. */
        fmt::text_style success;
        /** Something that is impossible or does not exsist. */
        fmt::text_style failure;
        /** Refers to external ecosystem. */
        fmt::text_style external;
        /** Information that was already shown (for. */
        fmt::text_style shown;
        /** Some action is safe or trusted. */
        fmt::text_style safe;
        /** Some action is unsafe or not trusted. */
        fmt::text_style unsafe;


        /** Reference to some input from the user. */
        fmt::text_style user;
        /** Input from the user was ignored or has no effect. */
        fmt::text_style ignored;
        /** Something was added due to user input. */
        fmt::text_style addition;
        /** Something was removed due to user input. */
        fmt::text_style deletion;

        /** The color of an empty progress bar. */
        fmt::text_style progress_bar_none;
        /** The color of the downloaded items in the progress bar. */
        fmt::text_style progress_bar_downloaded;
        /** The color of the extracted items in the progress bar. */
        fmt::text_style progress_bar_extracted;

        /** A Palette with no colors at all. */
        static constexpr Palette no_color();
        /** A Palette with terminal 4 bit colors. */
        static constexpr Palette terminal();
    };

    /*******************************
     *  Implementation of Palette  *
     *******************************/

    inline constexpr Palette Palette::no_color()
    {
        return {};
    }

    inline constexpr Palette Palette::terminal()
    {
        return {
            /* .success= */ fmt::fg(fmt::terminal_color::green),
            /* .failure= */ fmt::fg(fmt::terminal_color::red),
            /* .external= */ fmt::fg(fmt::terminal_color::cyan),
            /* .shown= */ fmt::fg(fmt::terminal_color::bright_black),
            /* .safe= */ fmt::fg(fmt::terminal_color::green),
            /* .unsafe= */ fmt::fg(fmt::terminal_color::red),
            /* .user= */ fmt::fg(fmt::terminal_color::blue) | fmt::emphasis::bold,
            /* .ignored= */ fmt::fg(fmt::terminal_color::yellow),
            /* .addition= */ fmt::fg(fmt::terminal_color::green),
            /* .deletion= */ fmt::fg(fmt::terminal_color::red),
            /* .progress_bar_none= */ fmt::fg(fmt::terminal_color::bright_black),
            /* .progress_bar_downloaded= */ fmt::fg(fmt::terminal_color::yellow),
            /* .progress_bar_extracted= */ {},
        };
    }

}
#endif
