**Contents**

* Running Deployment tool backend

  * The backend server will run on the port defined at the env variable DEPLOYMENT_TOOL_BACKEND_PORT in docker-compose.yml
  * Steps to run the tool
    ```
    cd IEdgeInsight/deployment-tool-backend
    ./run.sh
    ```
    * To build and run:
      ```
      ./run.sh --build
      ```

       or
      ```
      ./run.sh -b
      ```
    * To build & run with --no-cache or to provide any other build argument, just append the same after the above commands
    * for e.g. 
      ```
      ./run.sh --build --no-cache
      ```
      

