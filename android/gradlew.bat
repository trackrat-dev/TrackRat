@rem
@rem Copyright 2015 the original author or authors.
@rem
@rem Licensed under the Apache License, Version 2.0 (the "License");
@rem you may not use this file except in compliance with the License.
@rem You may obtain a copy of the License at
@rem
@rem      https://www.apache.org/licenses/LICENSE-2.0
@rem
@rem Unless required by applicable law or agreed to in writing, software
@rem distributed under the License is distributed on an "AS IS" BASIS,
@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
@rem See the License for the specific language governing permissions and
@rem limitations under the License.
@rem

@rem
@rem This script is used to run Gradle builds from the command line.
@rem It downloads and uses a specific version of Gradle, ensuring build consistency.
@rem

@echo off

setlocal

rem Determine the Java command to use to start the JVM.
if defined JAVA_HOME (
    set JAVACMD="%JAVA_HOME%\bin\java.exe"
) else (
    set JAVACMD=java
)

where %JAVACMD% >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
    echo Please set the JAVA_HOME variable in your environment to match the location of your Java installation.
    goto :eof
)

rem Determine the script directory.
set APP_HOME=%~dp0

rem Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass any JVM options to this script.
set DEFAULT_JVM_OPTS=-Xmx64m -Xms64m

rem Determine the Gradle wrapper JAR file.
set GRADLE_WRAPPER_JAR=%APP_HOME%gradle\wrapper\gradle-wrapper.jar

rem Execute Gradle.
"%JAVACMD%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% -classpath "%GRADLE_WRAPPER_JAR%" org.gradle.wrapper.GradleWrapperMain %*

endlocal
