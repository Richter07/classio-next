import { Link } from "react-router-dom";
import { Icon } from "../../shared/ui/Icon";

/** Adresse de contact de Classio pour les questions de données personnelles. À renseigner avant
 *  l'ouverture (voir docs/06-dossier-juridique.md, « Avant le lancement »). */
const CONTACT = "donnees@classio.bj";

/** Politique de confidentialité, version 2026-11-v1 (Code du numérique, loi n° 2017-20, Livre V).
 *  Tout changement de fond : changer PRIVACY_VERSION dans backend/config/settings.py. */
export function Privacy() {
  return (
    <main className="content prose">
      <Link to="/" className="back">
        <Icon name="back" /> Retour
      </Link>
      <h1>Politique de confidentialité</h1>
      <p className="muted">Version du 12 novembre 2026.</p>

      <h2>Qui est responsable de vos données ?</h2>
      <p>
        <strong>L'école de votre enfant.</strong> C'est elle qui décide quelles données sont utilisées et pourquoi : elle est
        « responsable du traitement » au sens du Code du numérique du Bénin (loi n° 2017-20, Livre V). Classio est son
        prestataire : nous hébergeons et faisons fonctionner l'application pour son compte, selon ses instructions, dans le
        cadre d'un contrat de sous-traitance. Nous n'utilisons jamais ces données pour nous-mêmes.
      </p>

      <h2>Quelles données ?</h2>
      <ul>
        <li>
          <strong>Votre enfant :</strong> nom, prénoms, date de naissance, sexe (si l'école le renseigne), matricule, classe,
          notes, absences aux évaluations, moyennes, rangs, appréciations et bulletins.
        </li>
        <li>
          <strong>Vous :</strong> nom, numéro de téléphone, lien avec l'élève, et la date à laquelle vous avez ouvert votre
          compte et lu cette politique. Votre mot de passe est conservé sous une forme chiffrée que personne ne peut relire, pas
          même Classio.
        </li>
      </ul>
      <p>Aucune photo, aucune donnée de santé, de religion ou d'origine. Ni publicité, ni revente, ni profilage.</p>

      <h2>Pourquoi ?</h2>
      <p>
        Pour que l'école gère les notes, calcule les moyennes et les rangs, établisse les bulletins et vous les communique.
        C'est une partie de la mission d'enseignement de l'école et de votre inscription : elle n'a pas besoin de votre
        consentement pour cela (article 389 du Code du numérique). Nous vous demandons seulement de confirmer que vous avez lu
        cette page.
      </p>

      <h2>Qui y a accès ?</h2>
      <ul>
        <li>Vous : les notes publiées par l'école pour vos propres enfants, puis leur bulletin quand l'école le publie.</li>
        <li>Chaque enseignant : uniquement ses classes et ses matières.</li>
        <li>La direction et le secrétariat : les données de leur école.</li>
        <li>
          L'équipe Classio : aucun accès courant. Pour une demande d'assistance seulement, avec l'accord de l'école, et cet
          accès est enregistré.
        </li>
      </ul>
      <p>Une école ne voit jamais les données d'une autre école.</p>

      <h2>Où sont-elles conservées ?</h2>
      <p>
        Sur un serveur situé dans un pays membre de la CEDEAO, avec des sauvegardes chiffrées. Elles ne sont pas transférées
        hors de la CEDEAO.
      </p>

      <h2>Combien de temps ?</h2>
      <ul>
        <li>Notes et bulletins : pendant la scolarité de l'enfant dans l'école, puis un an après son départ.</li>
        <li>Votre compte : tant qu'un de vos enfants est inscrit dans une école qui utilise Classio.</li>
        <li>Notifications : 400 jours. Sauvegardes : 30 jours.</li>
      </ul>
      <p>Les bulletins que l'école doit archiver au-delà sont conservés par l'école elle-même, pas par Classio.</p>

      <h2>Sécurité</h2>
      <p>
        Connexion chiffrée (HTTPS), sauvegardes chiffrées, accès limité selon le rôle de chacun, et un journal qui garde la
        trace de toute modification d'une note. En cas d'incident touchant vos données, l'école et l'Autorité de protection
        des données personnelles (APDP) sont prévenues sans délai, et vous aussi lorsque c'est nécessaire.
      </p>

      <h2>Vos droits</h2>
      <p>
        Vous pouvez demander à consulter les données de votre enfant et les vôtres, à les faire corriger, ou à les faire
        supprimer quand elles ne sont plus nécessaires. Adressez-vous au secrétariat de l'école, qui est responsable de ces
        données. Vous pouvez aussi écrire à Classio : <strong>{CONTACT}</strong>. Nous transmettons à l'école et vous
        répondons dans les 30 jours.
      </p>
      <p>
        Si vous estimez que vos droits ne sont pas respectés, vous pouvez saisir l'Autorité de protection des données
        personnelles (APDP), à Cotonou : apdp.bj.
      </p>

      <h2>Changements</h2>
      <p>Si cette politique change sur le fond, nous vous le signalerons dans l'application avant qu'elle s'applique.</p>
    </main>
  );
}
