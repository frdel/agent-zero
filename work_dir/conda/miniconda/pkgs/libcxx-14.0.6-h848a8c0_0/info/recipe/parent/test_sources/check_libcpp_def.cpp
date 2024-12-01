#include <iostream>

int main() {
#ifdef _LIBCPP_VERSION
    std::cout << "_LIBCPP_VERSION is " << _LIBCPP_VERSION << std::endl;
    return 0;
#else
    std::cout << "_LIBCPP_VERSION is undefined." << std::endl;
    return 1;
#endif  // _LIBCPP_VERSION
}
