# Coding Conventions

## General

VTK is a large body of code with many users and developers. Coding in a
consistent style eases shared development. VTK's style guidelines also
ensure wide portability. All code that is contributed to VTK must
conform to the following style guidelines. Exceptions are permissible,
following discussion in code review, as long as the result passes the
nightly regression tests. External code contributed into the ThirdParty
directory is exempt from most of the following rules except for the
rules that say "All code".

1. All code that is compiled into VTK by default must be compatible with VTK's BSD- style license.
1. Copyright notices should appear at the top of C++ header and implementation files using SPDX syntax.
1. All C++ code must be valid C++11 code.
1. The Java and Python wrappers must work on new code, or it should be excluded from wrapping.
1. Multiple inheritance is not allowed in VTK classes.

    Rationale: One important reason is that Java does not support it.
1. Only one public class per header file. Internal helper classes may be forward declared in header files, but can then only be defined in implementation files, ie using the PIMPL idiom.

    Rationale: helpful when searching the code and limits header inclusion bloat that slows compilation time.

1. Class names and file names must match, class names must be unique.

    Rationale: helpful when searching the code, includes are flattened at install.

1. The indentation style can be characterized as the modified Allman (https://en.wikipedia.org/wiki/Indent_style#Allman_style)style. Indentations are two spaces, and the curly brace (scope delimiter) is placed on the following line and indented to the same level as the control statement.

    Rationale: Readability and historical

1. Conditional clauses (including loop conditionals such as for and while) must be in braces below the conditional.
   Ie, instead of `if (test) clause` or `if (test) { clause }`, use
   ```cpp
   if (test)
   {
     clause
   }
   ```
     Rationale: helpful when running code through a debugger

1. Two space indentation. Tabs are not allowed. Trailing whitespace is not allowed.

   Rationale:  Removing tabs ensures that blocks are indented consistently in all editors.

1. Only alphanumeric characters in names. Use capitalization to demarcate words within a name (i.e., camel case). Preprocessor variables are the exception, and should be in all caps with a single underscore to demarcate words.

   Rationale: Readability

1. Every class, macro, etc starts with either vtk or VTK. Classes should all start with lowercase vtk and macros or constants can start with either.

   Rationale: avoids name clashes with other libraries

1. After the `vtk` prefix, capitalize the first letter of class names, methods and static and instance variables. Local variables are allowed to vary, but ideally should start in lower case and then proceed in camel case.

   Rationale: Readability

1. Try to always spell out a name and not use abbreviations except in cases where the shortened form is obvious and widely understood.

   Rationale: Readability, self-documentation

1. Classes that derive from `vtkObject` should have protected constructors and destructors, and privately declared but unimplemented copy constructor and assignment operator.

    1. Classes that don't derive from `vtkObject` should obey the rule of three. If the class implements the destructor, copy constructor or copy assignment operator they should implement all of them.

   Rationale: VTK's reference counting implementation depends on carefully controlling each object's lifetime.

1. Following the copyright notice, the name and purpose of each class should be documented at the top of the header with standard doxygen markup.:
    ```cpp
    /**
     * @class vtkclassname
     * @brief one line description
     *
     * Longer description of class here.
    */
    ```

    Rationale: Doxygen generated documentation uses this to describe each class.

1.  Public methods must be documented with doxygen markup.
    ```cpp
    /**
     * Explanation of what the method/ivar is for
     */
    ```
    Descriptions should do more than simply restate the method or ivar's name.

    The documentation for each public ivar should document the default value.

    The documentation style for SetGet macros should be a single comment for the pair and a brief description of the variable that is being set/get. Use doxygen group marking to make the comment apply to both macro expanded functions.

    ```cpp
    ///@{
    /**
     * Set / get the sharpness of decay of the splats.
     * This is the exponent constant in the Gaussian
     * equation. Normally this is a negative value.
     */
     */
    vtkSetMacro(ExponentFactor,double);
    vtkGetMacro(ExponentFactor,double);
    ///@}
    ```

    The documentation style for vector macros is to name each of the resulting variables. For example comment
    ```cpp
    /**
     * Set/Get the color which is used to draw shapes in the image. The parameters are SetDrawColor(red, green, blue, alpha)
     */
    vtkSetVector4Macro(DrawColor, double);
    vtkGetVector4Macro(DrawColor, double);
    ```

    The description for SetClamp macros must describe the valid range of values.
    ```cpp
    /**
     * Should the data with value 0 be ignored? Valid range (0, 1).
     */
    vtkSetClampMacro(IgnoreZero, int, 0, 1);
    vtkGetMacro(IgnoreZero, int);
    ```

    Rationale: Doxygen generated documentation (http://www.vtk.org/doc/nightly/html/) is generated from these comments and should be consistently readable.

1. Public and even Protected instance variables are allowed only in exceptional situations. Private variables should be used instead with public access given via Set/Get macro methods when needed.
   Rationale: Consistent API, ease of deprecation, and SetMacro takes part in reference counting.

1. Protected methods are allowed only when they are intended to be used by inheriting classes and overridden by inheriting classes. Private methods should be the default for any method.
   Please note this is not true in many classes but should be followed when adding new code.
   Rationale: Consistent API, ease of deprecation.

1. Accessors to `vtkObject` instance variables should be declared in the header file, and defined in the implementation file with the vtkCxxSetObjectMacro.
   Rationale: Reduces header file bloat and assists in reference counting.

1. Use `this->` inside of methods to access class methods and instance variables.
   Rationale: Readability as it helps to distinguish local variables from instance variables.

1. Header files should normally have just two includes, one for the superclass' header file and one for the class' module export header declaration. It is required that all but the superclass header have a comment explaining why the extra includes are necessary. Care should be taken to minimize the number of includes in public headers, with predeclaration/PIMPL preferred.
   Rationale: limits header inclusion bloat that slows compilation time.

1. Include statements in implementation files should generally be in alphabetical order, grouped by type. For example, VTK includes first, system includes, STL includes, and Qt includes.
   Rationale: avoid redundant includes, and keep a logical order.

1. All subclasses of `vtkObject` should include a `PrintSelf()` method that prints all publicly accessible ivars.

   Rationale: useful in debugging and in wrapped languages that lack sufficient introspection.
1. All subclasses of `vtkObject` should include a type macro in their class declaration.

   Rationale: VTK's implementation of runtime type information depends on it
1. Do not use `id` as a variable name in public headers, also avoid `min`, `max`, and other symbols that conflict with the Windows API.

   Rationale: `id` is a reserved word in Objective-C++, and against variable name rules. `min`, `max`, and less common identifiers listed in Testing/Core/WindowsMangleList.py are declared in the Windows API.

1. Prefer the use of vtkNew when the variable would be classically treated as a stack variable.

1. Eighty character line width is preferred.

   Rationale: Readability

1. Method definitions in implementation files should be preceded by // followed by 78 `-` characters.

   Rationale: Readability

1. New code must include regression tests that will run on the dashboards. The name of the file to test vtkClassName should be TestClassName.cxx. Each test should call several functions, each as short as possible, to exercise a specific functionality of the class. The `main()` function of the test file must be called TestClassName(int, char*[])

   Rationale: Code that is not tested can not be said to be working.

1. All code must compile and run without warning or error messages on the nightly dashboards, which include Windows, Mac, Linux and Unix machines. Exceptions can be made, for example to exclude warnings from ThirdParty libraries, by adding exceptions to CMake/CTestCustom.cmake.in

1. Namespaces should not be brought into global scope in any public headers, i.e. the `using` keyword should not appear in any public headers except within class scope. It can be used in implementations, but it is preferred to bring symbols into the global scope rather than an entire namespace.

   Rationale: Using VTK API should not have side-effects where parts of the std namespace (or the entire thing) are suddenly moved to global scope.

1. While much of the legacy VTK API uses integers for boolean values, new interfaces should prefer the bool type.

   Rationale: Readability.

1. Template classes are permitted, but must be excluded from wrapped languages.

   Rationale: The concept of templates doesn't exist in all wrapped languages.

1. Prefer overloading functions to default arguments.

   Rationale: Default function arguments in C++ are a tempting way to add an argument to a function while maintaining easy backwards compatibility. However, if you later want to add another argument to the list in a way that preserves backwards compatibility, it, too, must be a default argument. To supply the second of these arguments in a call forces you to also supply the first argument, even if it is the default value. As a result, this is not a clean way to add a argument to a function. Insetad, function overloading should be preferred.

## Specific C++  Language Guidelines
### C++ Standard Library

* Do not use vtkStdString in new API; prefer std::string

  Rationale: vtkStdString was introduced as a workaround for compilers that couldn’t handle the long symbol name for the expanded std::string type. It is no longer needed on modern platforms.

* STL usage in the Common modules' public API is discouraged when possible, Common modules are free to use STL in  implementation files. The other modules may use STL, but should do so only when necessary if there is not an appropriate VTK class. Care should be taken when using the STL in public API, especially in the context of what can be wrapped.

    Exception: std::string should be used as the container for all 8-bit character data, and is permitted throughout VTK.

    Rationale: limits header inclusion bloat, wrappers are not capable of handling many non-`vtkObject` derived classes.

* References to STL derived classes in header files should be private. If the class is not intended to be subclassed it is safe to put the references in the protected section.

    Rationale: avoids DLL boundary issues.


### C++ Language Features Required when using VTK

* [*nullptr*](http://en.cppreference.com/w/cpp/language/nullptr) Use `nullptr` instead of `0` and `NULL` when dealing with pointer types
* [*override*](http://en.cppreference.com/w/cpp/language/override)  `VTK_OVERRIDE` will be replaced with the override keyword
* [*final*](http://en.cppreference.com/w/cpp/language/final)  `VTK_FINAL` will be replaced with the final keyword
* [*delete*](http://en.cppreference.com/w/cpp/language/function#Deleted_functions) The use of delete is preferred over making default members private and unimplemented.

### C++11 Features allowed throughout VTK

* [*default*](http://en.cppreference.com/w/cpp/language/default_constructor)  The use of default is encouraged in preference to empty destructor implementations
* [*static_assert*](http://en.cppreference.com/w/cpp/language/static_assert) Must use the static_assert ( `bool_constexpr` , `message` ) signature. The signature without the message in c++17
* [*non static data member initializers*](http://en.cppreference.com/w/cpp/language/data_members)
* [*strongly typed enums*](http://en.cppreference.com/w/cpp/language/enum)
  VTK prefers the usage of strongly typed enums over classic weakly
  typed enums.

  Weakly typed enums conversion to integers is undesirable, and the
  ability for strongly typed enums to specify explicit storage size
  make it the preferred form of enums.

  strongly typed: `enum class Color { red, blue };`

  weakly typed: `enum Color { red, blue };`

  While VTK is aware that conversion of all enums over to strongly
  typed enums will uncover a collection of subtle faults and incorrect
  assumptions. Converting existing classes to use strongly typed enums
  will need to be investigated and discussed with the mailing list, as
  this will break API/ABI, potentially cause issues with VTK bindings,
  and possibly require changes to users VTK code.

### C++11 Features acceptable in VTK implementation files, private headers, and template implementations

* [*auto*](http://en.cppreference.com/w/cpp/language/auto)
  Use auto to avoid type names that are noisy, obvious, or unimportant - cases where the type doesn't aid in clarity for the reader.
  auto is permitted when it increases readability, particularly as described below. **Never initialize an auto-typed variable with a braced initializer list.**

  Specific cases where auto is allowed or encouraged:
  - (Encouraged) For iterators and other long/convoluted type names, particularly when the type is clear from context (calls to find, begin, or end for instance).
  - (Allowed) When the type is clear from local context (in the same expression or within a few lines). Initialization of a pointer or smart pointer with calls to new commonly falls into this category, as does use of auto in a range-based loop over a container whose type is spelled out nearby.
  - (Allowed) When the type doesn't matter because it isn't being used for anything other than equality comparison.
  - (Encouraged) When iterating over a map with a range-based loop (because it is often assumed that the correct type is std::pair<KeyType, ValueType> whereas it is actually std::pair<const KeyType, ValueType>). This is particularly well paired with local key and value aliases for .first and .second (often const-ref).
  - ```cpp
    for (const auto& item : some_map) {
    const KeyType& key = item.first;
    const ValType& value = item.second;
    // The rest of the loop can now just refer to key and value,
    // a reader can see the types in question, and we've avoided
    // the too-common case of extra copies in this iteration.
    }
    ```
  - (Discouraged) When iterating in integer space. `for (auto i=0; i < grid->GetNumberOfPoints(); ++i)`. Because vtk data structures usually contain more than 2 billion elements, iterating using 32bit integer is discouraged (and often doesn’t match the type used)

* [*braced initializer list*](http://en.cppreference.com/w/cpp/language/list_initialization)
   Braced initializer list are allowed as they prevent implicit narrowing conversions, and “most vexing parse” errors. They can be used when constructing POD’s  and other containers.

   **Braced initializer lists are not allowed to be used as the right hand side for auto:**

  ```cpp
    auto a = { 10, 20 }; //not allowed as a is std::initializer_list<int>
  ```

* [*lambda expressions*](http://en.cppreference.com/w/cpp/language/lambda)

  Usage of lambda expressions are allowed with the following guidelines.

   -  Use default capture by value ([=]) only as a means of binding a few variables for a short lambda, where the set of captured variables is obvious at a glance. Prefer not to write long or complex lambdas with default capture by value.
   - Except for the above, all capture arguments must be explicitly captured. Using the default capture by reference ([&]) is not allowed. This is to done so that it is easier to evaluate lifespan and reference ownership.
   - Keep unnamed lambdas short. If a lambda body is more than maybe five lines long, prefer using a named function instead of a lambda.
   - Specify the return type of the lambda explicitly if that will make it more obvious to readers.

* [*shared_ptr*](http://en.cppreference.com/w/cpp/memory/shared_ptr)
  - **Do not combine shared_ptr and vtk derived objects.** VTK internal reference counting makes the shared_ptr reference counting ( and destructor tracking ) pointless.


* [*unique_ptr*](http://en.cppreference.com/w/cpp/memory/unique_ptr)
  -   Do not combine unique_ptr and vtk derived objects.  We prefer using vtkNew as VTK objects use internal reference counting and custom deletion logic, the ownership semantics of unique_ptr are invalid.
  -   `make_unique` is not part of c++11 


* [*template alias*](http://en.cppreference.com/w/cpp/language/type_alias)
  - The use of alias templates is preferred over using 'typedefs'. They provide the same language pattern of normal declarations, and reduce the need for helper template structs. For example ( Scott Meyers, Effective Modern C++ )

  ```cpp
  template<typename T> using MyAllocList = std::list<T, MyAlloc<T>>;
  ```

* universal references (&&) / std::move / std::forward

* [*extern templates*](http://en.cppreference.com/w/cpp/language/class_template)

  - Note: This should be investigated as an update to the current infrastructure used to export explicit template instantiations used within VTK 

* [*unordered maps*](http://en.cppreference.com/w/cpp/concept/UnorderedAssociativeContainer)

* [*std::array* ](http://en.cppreference.com/w/cpp/container/array)

   - The use of std::array is preferred over using raw fixed sized arrays. They offer compile time bounds checking without any runtime cost. 

* [*range based for loop*](http://en.cppreference.com/w/cpp/language/range-for)

### C++11 Features allowed under certain conditions

* [*concurrency*](https://isocpp.org/wiki/faq/cpp11-library-concurrency)

  Concurrency inside of vtk should be handled by using or extending the already existing collection of support classes like vtkAtomic and vtkSMPThreadLocal.

  Instead of directly using new c++11 constructs such as std::compare_exchange_weak instead extend the functionality of vtk core concurrency classes.

  Note: Thread local storage has not been supported on OSX previously to XCode 8. VTK offers the following classes that should be used instead:

  -   [vtkSMPThreadLocalObject](http://www.vtk.org/doc/release/7.0/html/classvtkSMPThreadLocalObject.html)

  -   [vtkSMPThreadLocal](http://www.vtk.org/doc/release/6.3/html/classvtkSMPThreadLocal.html)

* [*std::isnan*](http://en.cppreference.com/w/cpp/numeric/math/isnan), [*std::isfinite*](http://en.cppreference.com/w/cpp/numeric/math/isfinite), [*std::isinf*](http://en.cppreference.com/w/cpp/numeric/math/isinf)

    These functions should not be called directly,  instead the wrapped versions provided by vtk should be used instead. 

    -   vtk::isnan -> std::isnan

    -   vtk::isfinite -> std::isfinite

    -   vtk::isisinfnan -> std::isinf

    The reason for these wrappings is to work around compiler performance issues. For example,  some clang version would convert integral types to double and do the operation on the double value, instead of simply returning false/true.

* [*std::future*](http://en.cppreference.com/w/cpp/thread/future)/ [*std::async*](http://en.cppreference.com/w/cpp/thread/async)

    Future/Async based programming inside of vtk should be handled on a case by case basis. In general the use cases for this kind of execution model is best applied at the vtkExecutive / vtkPipeline level, or at the File IO level. 

    In these cases the recommendation is to extending or adding support classes so that these design patterns can be utilized in the future.

* [*variadic templates*](http://en.cppreference.com/w/cpp/language/parameter_pack)

  Variadic Templates are not allowed in VTK unless they are the only solution to the given problem. 

### C++11 Features that are not allowed

* [std::regex](http://en.cppreference.com/w/cpp/regex)

  - Not supported by GCC 4.8 (can be used once GCC 4.9 is required)

Parts of this coding style are enforced by git commit hooks that are put in
place when the developer runs the SetupForDevelopment script, other parts
are enforced by smoke tests that run as part of VTK’s regression test suite.
Most of these guidelines are not automatically enforced.
[VTK’s commit hook enforced style checks Section](#vtks-commit-hook-enforced-style-checks) list the style checks that are in place.

#### VTK’s commit hook enforced style checks

* Well formed commit message

  Every commit message should consist of a one line summary optionally followed by a blank line and further details. This is most easily approximated to the subject of an email, and the body in the form of paragraphs.

*  Valid committer username and email address
  Every developer must have a valid name and email configured in git.\

* ASCII filename check
  All file names must contain only ASCII characters.

* No tabs

* No trailing whitespace

* No empty line at end of file

* Proper file access mode

  Files must be committed with sensible access modes.

* One megabyte maximum file size

* No submodules

  The VTK project allows only one submodule, [Viskores](https://github.com/Viskores/viskores) (formerly VTK-m, located in `ThirdParty/vtkm/vtkvtkm/vtk-m`). For other required third party dependencies, the recommended scheme is to use git's subtree merge strategy to reproducibly import code and thereby simplify eventual integration of upstream changes. Copies of these third party libraries with branches specifically for vendoring them in VTK are located in the [third-party](https://gitlab.kitware.com/third-party/) GitLab space.

Additionally, new developers should be aware that the regression test machines have fairly strict compiler warnings enabled and usually have VTK_DEBUG_LEAKS configured on to catch leaks of VTK objects. Developers should be in the habit of doing the same in their own environments so as to avoid pushing code that the dashboards will immediately object to. With GCC, it is easiest to do so by turning on VTK_EXTRA_COMPILER_WARNINGS.
