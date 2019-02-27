#!/usr/bin/env perl
#
# Generate an Anthology XML file from BibTeX files
#
# Usage: anthology-xml.pl bib_dir volume_id xml_file
#
# - bib_dir is usually called "bib" and contains one .bib file per
#   paper (or front matter)
# - volume_id is a three-character code like N18
# - xml_file is the generated XML file

use utf8;
use open qw(:std :utf8);

use strict 'vars';

use File::Spec;
use Text::BibTeX;

my ($dir, $volume_id, $outfile) = @ARGV;

# check ACLPUB path
die "Need to export ACLPUB=/path/to/acl-pub/assets/files/create_book"
  unless(-d $ENV{ACLPUB});

open XML, "| $ENV{ACLPUB}/bin/db-to-html.pl -f xml > $outfile";
print XML '<?xml version="1.0" encoding="UTF-8" ?>',"\n";
print XML " <volume id=\"$volume_id\">\n";
# XML to be continued

for my $bib (glob("$dir/*.bib")) {   # bib entry files in numerically sorted order
    chomp($bib);

    # Parse the bib entry.
    my $file = Text::BibTeX::File->new($bib);
    my $bibentry = Text::BibTeX::Entry->new({ binmode => 'utf-8', normalization => 'NFC' }, $file);
    
    my $url = $bibentry->get('url');
    my $paper_id;
    if ($url =~ m{^http://www.aclweb.org/anthology/([A-Z])(\d{2})-(\d{0,4})}) {
        $paper_id = $3;
        $paper_id .= "0" while (length($paper_id) < 4);
    } else {
        die "Aborting: $url in $bib is not a valid ACL Anthology URL\n"
    }

    # Convert the current .bib file into XML.

    print XML "   <paper id=\"$paper_id\">\n";

    my %alreadydone;
    for my $field ('title', 'author', 'editor', $bibentry->fieldlist) {   # force order
      next unless $bibentry->exists($field);
      next if $alreadydone{$field}++;
      my @values = ($field eq 'author' || $field eq 'editor')
               	       ? map { &formatname($_) } $bibentry->names($field)
		       : &escape_xml($bibentry->get($field));
      for my $val (@values) {
	print XML "        <$field>$val</$field>\n";
      }
    }
    print XML "        <bibtype>".$bibentry->type."</bibtype>\n";
    print XML "        <bibkey>".$bibentry->key."</bibkey>\n";
    print XML "   </paper>\n";
}

print XML " </volume>\n";
close(XML);

###############

# produce name in format <first>Ludwig</first><last>van Beethoven</last>
# bibtex has fields for fist, von, last, and jr
# but anthology database only has fields for first and last.

# We could use Text::BibTeX::NameFormat for this, i.e.,
#     my $format = new Text::BibTeX::NameFormat ('fvlj',0);
#     return $format->apply($name);
# However, customizing that to put XML tags around the pieces is too annoying.

sub formatname {
  my($name) = @_;
  my @tokens = $name->part('first');
  my $out = "<first>".&escape_xml(join(" ",@tokens))."</first>";
  $out .= "<last>";
  @tokens = $name->part('von');
  if (@tokens && $tokens[0]) {   # nonempty
      $out .= &escape_xml(join(" ",@tokens));
      $out .= ' ';
  }
  @tokens = $name->part('last');
  $out .= &escape_xml(join(" ",@tokens));
  @tokens = $name->part('jr');
  if (@tokens && $tokens[0]) {   # nonempty
      # comma before Jr
      $out .= ", " . &escape_xml(join(" ",@tokens));
  }
  $out .= "</last>";    
  if ($out eq lc($out)) {
      # some authors have all lowercase names in their softconf profiles
      # which triggers a bug in TeX::BibTeX name parsing
      # https://github.com/ambs/Text-BibTeX/issues/29
      warn "Lowercase name: $out\n Name may be duplicated/misparsed";
  }
  return $out;
}

sub escape_xml {
    my($text) = @_;
    $text =~ s/&/&amp;/go;
    $text =~ s/</&lt;/go;
    $text =~ s/>/&gt;/go;
    $text =~ s/'/&apos;/go;
    $text =~ s/"/&quot;/go;
    return $text;
}
