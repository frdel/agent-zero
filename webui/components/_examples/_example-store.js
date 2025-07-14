import { createStore } from "/js/AlpineStore.js";

// define the model object holding data and functions
const model = {
    example1:"Example 1",
    example2:"Example 2",

    // gets called when the store is created
    init(){
        console.log("Example store initialized");
    }

};

// convert it to alpine store
const store = createStore("_exampleStore", model);

// export for use in other files
export { store };
