#include <cassert>
#include <yaml-cpp/yaml.h>

int main()
{
    YAML::Node node = YAML::Load("[1, 2, 3]");

    assert(node.IsSequence());

    return 0;
}
