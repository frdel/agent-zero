#include "mamba_fs.hpp"
#include "transaction_context.hpp"

namespace mamba
{
    void remove_menu_from_json(const fs::u8path& json_file, TransactionContext* context);
    void create_menu_from_json(const fs::u8path& json_file, TransactionContext* context);
#ifdef _WIN32
    namespace win
    {
        fs::u8path get_folder(const std::string& id);
    }

#endif
}
