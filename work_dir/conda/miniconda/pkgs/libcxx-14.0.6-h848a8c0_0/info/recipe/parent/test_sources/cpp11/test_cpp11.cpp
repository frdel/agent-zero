#include <atomic>
#include <unordered_map>
#include <unordered_set>
#include <regex>
#include <iostream>

int main() {
    auto lambda_func = [](int x, int y) -> int { return x + y; };
    std::cout << lambda_func(1, 2) << std::endl;
    return 0;
}
