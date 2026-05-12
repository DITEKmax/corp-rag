package com.corprag.service.user;

import java.security.SecureRandom;
import org.springframework.stereotype.Component;

@Component
public class TemporaryPasswordGenerator {

    private static final char[] UPPERCASE = "ABCDEFGHJKLMNPQRSTUVWXYZ".toCharArray();
    private static final char[] LOWERCASE = "abcdefghijkmnopqrstuvwxyz".toCharArray();
    private static final char[] DIGITS = "23456789".toCharArray();
    private static final char[] ALPHABET =
            "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789".toCharArray();
    private static final int LENGTH = 16;

    private final SecureRandom secureRandom = new SecureRandom();

    public String generate() {
        char[] chars = new char[LENGTH];
        chars[0] = randomChar(UPPERCASE);
        chars[1] = randomChar(LOWERCASE);
        chars[2] = randomChar(DIGITS);
        for (int index = 3; index < chars.length; index++) {
            chars[index] = randomChar(ALPHABET);
        }
        for (int index = chars.length - 1; index > 0; index--) {
            int swapIndex = secureRandom.nextInt(index + 1);
            char current = chars[index];
            chars[index] = chars[swapIndex];
            chars[swapIndex] = current;
        }
        return new String(chars);
    }

    private char randomChar(char[] alphabet) {
        return alphabet[secureRandom.nextInt(alphabet.length)];
    }
}
