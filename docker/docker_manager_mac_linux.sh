#!/bin/bash

# Constants
IMAGE_NAME="agent-zero-run"
DEFAULT_CONTAINER_NAME="agent-zero"
BASE_PORT=50080

# Global variable for container IDs
container_ids=()

# Function to list unique containers based on the specified image
list_containers() {
    echo
    echo "Listing all containers using image '$IMAGE_NAME':"
    container_ids=()  # Reset global array for each list update
    container_list=$(docker ps -a --filter "ancestor=$IMAGE_NAME" --format "{{.ID}} {{.Names}} {{.Ports}}" | sort -u -k2,2)

    if [ -z "$container_list" ]; then
        echo "No containers found for image '$IMAGE_NAME'."
        return 1
    fi

    index=1
    printed_ids=()
    while IFS= read -r line; do
        container_id=$(echo "$line" | awk '{print $1}')
        container_name=$(echo "$line" | awk '{print $2}')
        ports=$(echo "$line" | awk '{print substr($0, index($0,$3))}')

        # Extract the mapped port using sed
        mapped_port=$(echo "$ports" | sed -n 's/.*0.0.0.0:\([0-9]*\)->80.*/\1/p')
        container_url="http://localhost:${mapped_port}"

        # Check if this ID has already been printed and mapped_port is valid
        if [[ ! " ${printed_ids[@]} " =~ " ${container_id} " ]] && [ -n "$mapped_port" ]; then
            printed_ids+=("$container_id")
            container_ids+=("$container_id")  # Store container ID in global array
            printf "%2d. [%s] %s - URL: %s\n" "$index" "$container_id" "$container_name" "$container_url"
            index=$((index + 1))
        fi
    done <<< "$container_list"
    return 0
}



# Function to select an action for an existing container
manage_container() {
    container_id=$1
    while true; do
        echo -e "\nSelect an action for container ID: $container_id"
        echo "1. Restart"
        echo "2. Remove"
        echo "3. View Logs"
        echo "0. Back"
        read -p "Choose an action (0-3): " action
        case $action in
            1) 
                docker restart "$container_id"
                echo "Container restarted."
                ;;
            2) 
                docker rm -f "$container_id"
                echo "Container removed."
                return  # Go back to the list screen after removing
                ;;
            3)
                echo -e "\n--- Logs for container ID: $container_id ---"
                docker logs "$container_id"
                echo -e "\n--- End of logs ---"
                ;;
            0)
                return
                ;;
            *)
                echo "Invalid selection. Please choose 0, 1, 2, or 3."
                ;;
        esac
    done
}

# Function to create a new container
create_container() {
    # Generate the default container name
    container_count=$(docker ps -a --filter "name=$DEFAULT_CONTAINER_NAME" --format "{{.Names}}" | wc -l)
    default_name="$DEFAULT_CONTAINER_NAME-$(($container_count + 1))"
    
    # Prompt for the container name
    read -p "Enter container name or leave empty for '$default_name': " name
    name=${name:-"$default_name"}

    # Calculate default port based on the container count
    default_port=$((BASE_PORT + container_count + 1))
    read -p "Enter web port or leave empty for '$default_port': " web_port
    web_port=${web_port:-$default_port}

    # Prompt for the data folder
    read -p "Enter data folder or leave empty for '$(pwd)/agent-zero': " data_folder
    data_folder=${data_folder:-$(pwd)/agent-zero}

    # Run the container with the specified name, port mapping, and data folder
    container_id=$(docker run -d -p "$web_port:80" --name "$name" -v "$data_folder:/a0" "$IMAGE_NAME:latest")
    echo -e "\nContainer '$name' created with ID '$container_id', data folder '$data_folder', and web port '$web_port' mapped to port 80."
}

# Main program loop
echo -e "\nWelcome to Agent Zero Docker Management Script.\n"
while true; do
    list_containers
    if [ $? -ne 0 ]; then
        echo -e "\nNo containers available. Would you like to create a new one? (y/n)"
        read -p "> " create_new
        if [ "$create_new" == "y" ]; then
            create_container
        else
            exit 0
        fi
    else
        echo -e "\nChoose a container by line number, type 'n' to create a new one, or 'r' to refresh the list:"
        read -p "> " choice

        # Refresh the list if the user inputs 'r'
        if [ "$choice" == "r" ]; then
            continue
        fi

        # Match choice to the actual container list
        if [[ $choice =~ ^[0-9]+$ ]] && ((choice >= 1 && choice <= ${#container_ids[@]})); then
            selected_container_id="${container_ids[$((choice - 1))]}"
            manage_container "$selected_container_id"
        elif [ "$choice" == "n" ]; then
            create_container
        else
            echo "Invalid choice, please enter a valid line number, 'n' to create a new container, or 'r' to refresh the list."
        fi
    fi
done
