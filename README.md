**Contents**

# Running Deployment tool backend

## Prerequisites
    
   Please ensure that all the pre-requisites needed for EII are installed. Please refer to [EII README](https://github.com/open-edge-insights/eii-core/blob/master/README.md) for more details.

## Configuration

  * The backend server will run on the port defined at the env variable DEPLOYMENT_TOOL_BACKEND_PORT in docker-compose.yml
  * The backend server will run in dev mode (http/insecure) or prod mode (https/secure) depending on the env variable DEV_MODE in docker-compose.yml. As of now only dev mode is supported.

    ```
    DEV_MODE: "true"
    ```
  * Logging can be configured by setting the env variable LOG_LEVEL in docker-compose.yml.

    ```
    LOG_LEVEL: "INFO"
    ```
    The following log levels are supported:

    * DEBUG
    * INFO
    * ERROR


## Running the tool

  * **Steps to run the tool**

    * **To simply run the container (without building)**:

      ```shell
      $ cd [WORKDIR]/IEdgeInsights/DeploymentToolBackend
      $ ./run.sh
      ```

    * **To build and run**:
      ```shell
      $ ./run.sh --build
      ```
       or
      ```shell
      $ ./run.sh -b
      ```

      To build & run with --no-cache or to provide any other build argument, just append the same after the above commands.

      for e.g. 

      ```shell
      $ ./run.sh --build --no-cache
      ```
      Note: If you are building the container for the first time, it may prompt you for the host user password and also credentials for SSH key generation. The host user will then be added to sudoers with NOPASSWORD option. This is for the container to seemlessly interact with the host.

    * **To restart the container:**

      ```shell
      $ ./run.sh --restart
      ```
       or
      ```shell
      $ ./run.sh -r
      ```

    * **To bring down the container:**

      ```shell
      $ ./run.sh --down
      ```
       or
      ```shell
      $ ./run.sh -d
      ```
      
## API Documentation

  The tool auto-generates OpenAPI documentation for all the REST APIs it exposes.
  This documentation can be accessed at its **/docs** endpoint.

  for e.g. 
    ```
    http://127.0.0.1:5100/docs
    ```
