package com.corprag.service.user;

import java.security.SecureRandom;
import org.springframework.stereotype.Component;

@Component
public class TemporaryPasswordGenerator {

    private static final char[] ALPHABET =
            "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%".toCharArray();
    private static final int LENGTH = 16;

    private final SecureRandom secureRandom = new SecureRandom();

    public String generate() {
        char[] chars = new char[LENGTH];
        for (int index = 0; index < chars.length; index++) {
            chars[index] = ALPHABET[secureRandom.nextInt(ALPHABET.length)];
        }
        return new String(chars);
    }
}
