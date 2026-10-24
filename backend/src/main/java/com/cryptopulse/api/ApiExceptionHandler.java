package com.cryptopulse.api;

import java.time.Instant;
import org.springframework.dao.DataAccessException;
import com.mongodb.MongoException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

@RestControllerAdvice
class ApiExceptionHandler {
    @ExceptionHandler({IllegalArgumentException.class, MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class})
    ResponseEntity<ApiModels.Error> invalid(Exception e) {
        String message = e instanceof MethodArgumentTypeMismatchException ? "Invalid parameter type"
                : e instanceof MissingServletRequestParameterException missing ? "Missing parameter: " + missing.getParameterName()
                : e.getMessage();
        return error(HttpStatus.BAD_REQUEST, "INVALID_ARGUMENT", message);
    }

    @ExceptionHandler({DataAccessException.class, MongoException.class})
    ResponseEntity<ApiModels.Error> unavailable(Exception e) {
        return error(HttpStatus.SERVICE_UNAVAILABLE, "DATA_UNAVAILABLE", "Market data is temporarily unavailable");
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<ApiModels.Error> missing() {
        return error(HttpStatus.NOT_FOUND, "NOT_FOUND", "Route not found");
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<ApiModels.Error> method() {
        return error(HttpStatus.METHOD_NOT_ALLOWED, "METHOD_NOT_ALLOWED", "HTTP method not supported for this route");
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiModels.Error> unexpected(Exception e) {
        return error(HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "Unable to read market data");
    }

    private ResponseEntity<ApiModels.Error> error(HttpStatus status, String code, String message) {
        return ResponseEntity.status(status).body(new ApiModels.Error(code, message, Instant.now()));
    }
}
