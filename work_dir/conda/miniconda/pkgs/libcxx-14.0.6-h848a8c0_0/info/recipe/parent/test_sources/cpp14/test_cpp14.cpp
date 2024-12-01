#include <shared_mutex>
#include <iostream>

int main() {
    auto lambda_func = [](auto x, auto y) -> auto { return x + y; };
    std::cout << lambda_func(1, 2) << std::endl;
    return 0;
}
