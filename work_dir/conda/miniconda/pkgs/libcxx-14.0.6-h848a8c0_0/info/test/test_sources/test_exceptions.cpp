#include <stdexcept>
#include <iostream>

int main() {
    try {
        throw std::runtime_error("Hello, I'm an exception!");
    } catch (std::runtime_error &e) {
        std::cout << e.what() << std::endl;
    }
    return 0;
}
