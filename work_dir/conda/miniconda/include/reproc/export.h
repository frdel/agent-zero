#pragma once

#ifndef REPROC_EXPORT
  #ifdef _WIN32
    #ifdef REPROC_SHARED
      #ifdef REPROC_BUILDING
        #define REPROC_EXPORT __declspec(dllexport)
      #else
        #define REPROC_EXPORT __declspec(dllimport)
      #endif
    #else
      #define REPROC_EXPORT
    #endif
  #else
    #ifdef REPROC_BUILDING
      #define REPROC_EXPORT __attribute__((visibility("default")))
    #else
      #define REPROC_EXPORT
    #endif
  #endif
#endif
