pipeline {
    agent any

    environment {
        DB_HOST = 'localhost'
        DB_USER = 'root'
        DB_PASSWORD = 'thejeswar'
        SECRET_KEY = 'testsecret123'
    }

    stages {

        stage('Setup Python') {
            steps {
                bat 'python --version'
                bat 'python -m pip --version'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt'
            }
        }

        stage('Env Check') {
            steps {
                bat 'echo DB_HOST=%DB_HOST%'
            }
        }

        stage('Run App Check') {
            steps {
                bat 'python -m py_compile app.py'
            }
        }
    }

    post {
        success {
            echo 'CI Pipeline Successful'
        }
        failure {
            echo 'CI Pipeline Failed'
        }
    }
}